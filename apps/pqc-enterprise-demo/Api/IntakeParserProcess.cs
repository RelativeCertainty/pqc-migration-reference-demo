using System.Diagnostics;
using System.Reflection;
using System.Text;
using System.Text.Json;

namespace PqcEnterpriseDemo.Api;

internal static class IntakeParserProcess
{
    private static readonly SemaphoreSlim Lane=new(1,1);
    private static readonly SemaphoreSlim CleanupWaiter=new(1,1);
    private static TaskCompletionSource<bool>? Cleanup;
    public static Task<IntakeWorkbookReturn> Parse(byte[] bytes,CancellationToken cancellation,bool questionnaire=false,bool discovery=false)
    {
        if(questionnaire&&discovery)throw new DemoValidationException("workbook_parser_mode_invalid");
        return ParseCore<IntakeWorkbookReturn>(bytes,cancellation,discovery?"--discovery-workbook-parser":questionnaire?"--questionnaire-workbook-parser":"--intake-workbook-parser");
    }
    public static Task<OperationalReturnDto> ParseOperational(byte[] bytes,CancellationToken cancellation)=>
        ParseCore<OperationalReturnDto>(bytes,cancellation,"--operational-workbook-parser");
    private static async Task<T> ParseCore<T>(byte[] bytes,CancellationToken cancellation,string mode) where T:class
    {
        if(bytes.Length>IntakeWorkbook.MaxInputBytes)throw new DemoValidationException("workbook_limits_exceeded");
        await AcquireLane(cancellation);
        var unit="pqc-intake-parser-"+Guid.NewGuid().ToString("N")+".service";
        try
        {
            using var deadline=CancellationTokenSource.CreateLinkedTokenSource(cancellation);deadline.CancelAfter(TimeSpan.FromSeconds(30));
            var start=new ProcessStartInfo("/usr/bin/systemd-run"){RedirectStandardInput=true,RedirectStandardOutput=true,RedirectStandardError=true,UseShellExecute=false};
            foreach(var arg in new[]{"--user","--quiet","--wait","--pipe","--collect","--unit="+unit,
                "--property=MemoryMax=512M","--property=MemorySwapMax=0","--property=CPUQuota=100%","--property=TasksMax=64",
                "--property=NoNewPrivileges=yes","--property=PrivateNetwork=yes","--property=RuntimeMaxSec=30s",
                "/usr/bin/env","-i","DOTNET_EnableDiagnostics=0","DOTNET_gcServer=0",
                Environment.ProcessPath ?? throw new DemoStoreException("intake_parser_runtime_unavailable"),
                Assembly.GetExecutingAssembly().Location,mode})start.ArgumentList.Add(arg);
            using var process=Process.Start(start) ?? throw new DemoStoreException("intake_parser_unavailable");
            try
            {
                var output=BoundedRead(process.StandardOutput.BaseStream,1_048_576,deadline.Token);
                var error=BoundedRead(process.StandardError.BaseStream,8192,deadline.Token);
                await process.StandardInput.BaseStream.WriteAsync(bytes,deadline.Token);process.StandardInput.Close();
                await process.WaitForExitAsync(deadline.Token);
                var result=await output;_=await error;
                if(process.ExitCode!=0)throw new DemoValidationException("workbook_rejected_or_parser_unavailable");
                return JsonSerializer.Deserialize<T>(result,AssessmentJson.Options) ?? throw new DemoValidationException("workbook_invalid");
            }
            catch(OperationCanceledException)
            {
                if(!process.HasExited)process.Kill(true);
                throw new DemoHttpException(408,"intake_parser_timeout");
            }
            catch
            {
                if(!process.HasExited)process.Kill(true);
                throw;
            }
        }
        finally
        {
            // The systemd client is not the parser's parent. Do not release the
            // single-parser lane until its exact owned service is known stopped.
            // If the manager becomes unreachable, intake stays closed until restart.
            var completion=new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
            Volatile.Write(ref Cleanup,completion);
            var released=false;
            try
            {
                if(await StopOwnedUnit(unit)){Lane.Release();released=true;}
            }
            finally
            {
                completion.TrySetResult(released);
                if(released)Interlocked.CompareExchange(ref Cleanup,null,completion);
            }
            if(!released)throw new DemoStoreException("intake_parser_cleanup_unconfirmed");
        }
    }
    private static async Task AcquireLane(CancellationToken cancellation)
    {
        if(await Lane.WaitAsync(0,cancellation))return;
        var completion=Volatile.Read(ref Cleanup);
        // An active parser never queues another parser. During cleanup only,
        // one caller can wait for the verified stop-and-release handoff. This
        // closes the gap where systemd already reports inactive but the final
        // manager check has not yet released the application semaphore.
        if(completion is null)
        {
            // Cleanup may have released the lane and cleared its marker
            // between the first acquisition attempt and this read.
            if(await Lane.WaitAsync(0,cancellation))return;
            throw new DemoHttpException(429,"intake_parser_busy");
        }
        if(!await CleanupWaiter.WaitAsync(0,cancellation))throw new DemoHttpException(429,"intake_parser_busy");
        try
        {
            using var deadline=CancellationTokenSource.CreateLinkedTokenSource(cancellation);
            deadline.CancelAfter(TimeSpan.FromSeconds(10));
            bool confirmed;
            try{confirmed=await completion.Task.WaitAsync(deadline.Token);}
            catch(OperationCanceledException)when(!cancellation.IsCancellationRequested)
            {throw new DemoHttpException(408,"intake_parser_cleanup_wait_timeout");}
            if(!confirmed)throw new DemoStoreException("intake_parser_cleanup_unconfirmed");
            if(!await Lane.WaitAsync(0,cancellation))throw new DemoHttpException(429,"intake_parser_busy");
        }
        finally{CleanupWaiter.Release();}
    }
    private static async Task<bool> StopOwnedUnit(string unit)
    {
        try
        {
            using var deadline=new CancellationTokenSource(TimeSpan.FromSeconds(8));
            async Task<string> Manager(params string[] arguments)
            {
                var info=new ProcessStartInfo("/usr/bin/systemctl"){RedirectStandardOutput=true,RedirectStandardError=true,UseShellExecute=false};
                info.ArgumentList.Add("--user");foreach(var arg in arguments)info.ArgumentList.Add(arg);info.ArgumentList.Add(unit);
                using var child=Process.Start(info)!;
                var output=BoundedRead(child.StandardOutput.BaseStream,4096,deadline.Token);
                var error=BoundedRead(child.StandardError.BaseStream,4096,deadline.Token);
                try{await child.WaitForExitAsync(deadline.Token);_=await error;return Encoding.UTF8.GetString(await output).Trim();}
                catch{if(!child.HasExited)child.Kill(true);throw;}
            }
            _=await Manager("stop");
            var status=await Manager("show","--property=ActiveState","--value");
            return status is "inactive" or "failed";
        }
        catch{return false;}
    }
    private static async Task<byte[]> BoundedRead(Stream input,int maximum,CancellationToken token)
    {
        using var output=new MemoryStream();var buffer=new byte[4096];int read;
        while((read=await input.ReadAsync(buffer,token))>0)
        {
            if(output.Length+read>maximum)throw new DemoValidationException("intake_parser_output_limit");
            output.Write(buffer,0,read);
        }
        return output.ToArray();
    }
    public static async Task<int> RunChild(bool questionnaire=false,bool discovery=false,bool operational=false)
    {
        try
        {
            var bytes=await BoundedRead(Console.OpenStandardInput(),1_048_576,CancellationToken.None);
            if(new[]{questionnaire,discovery,operational}.Count(value=>value)>1)throw new DemoValidationException("workbook_parser_mode_invalid");
            object parsed=operational?OperationalReturnWorkbook.Read(bytes):discovery?DiscoveryWorkbook.Read(bytes):questionnaire?QuestionnaireWorkbook.Read(bytes):IntakeWorkbook.Read(bytes);
            await Console.OpenStandardOutput().WriteAsync(JsonSerializer.SerializeToUtf8Bytes(parsed,AssessmentJson.Options));
            return 0;
        }
        catch(DemoValidationException e){await Console.Error.WriteAsync(e.Code);return 2;}
        catch{await Console.Error.WriteAsync("workbook_invalid");return 2;}
    }
}

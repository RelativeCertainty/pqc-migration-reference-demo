using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Xml;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Spreadsheet;
using DocumentFormat.OpenXml.Validation;

namespace PqcEnterpriseDemo;

public sealed record QuestionnaireWorkbookQuestion(string Id,string Prompt,string Section,string ResponseType,
    bool Required,string EvidenceExpectation,string CompletionCriteria,string WhyItMatters,string[] AllowedValues);
public sealed record QuestionnaireWorkbookAnswer(string DefinitionSha256,Dictionary<string,string> Fields,
    string AssessmentId,string AssignmentId,string TemplateId,string TemplateVersion,string TemplateSha256);

/// <summary>Closed, versioned full-questionnaire exchange; never an approval or generic workbook importer.</summary>
public static partial class QuestionnaireWorkbook
{
    public const string Format="pqc.questionnaire.return.v1";
    public static readonly string[] Fields=["status","text","evidenceRefs","rationale","nextOwner","nextDate","blocker","scheduleEffect","assertedBy","attestationOwner","attestationDate","attestationQualification"];
    private static readonly string[] Headers=["Question ID — do not edit","Exact question — do not edit","Response status","Response text","Evidence references — one per line","Rationale / qualification","Next responsible function","Next action date (YYYY-MM-DD)","Blocker","Schedule effect","Attributed statement by — unverified data","CQ-24 attestation owner — reported data","CQ-24 attestation date — reported data","CQ-24 qualification — reported data"];
    private static readonly string[] GuideHeaders=["Question ID","Section","Response type","Required?","Allowed values (one per line)","Required evidence / expected reference","Completion criteria","Why this matters"];
    [GeneratedRegex("^([A-N])([1-9][0-9]?)$",RegexOptions.CultureInvariant)] private static partial Regex CellPattern();
    [GeneratedRegex("^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$",RegexOptions.CultureInvariant)] private static partial Regex IdPattern();

    public static string DefinitionHash(QuestionnaireWorkbookQuestion q)=>Convert.ToHexStringLower(SHA256.HashData(JsonSerializer.SerializeToUtf8Bytes(q,AssessmentJson.Options)));

    public static byte[] Write(string exportId,string assessmentId,string assignmentId,string templateId,string version,string templateSha256,
        string deploymentLabel,IReadOnlyList<QuestionnaireWorkbookQuestion> questions,IReadOnlyDictionary<string,Dictionary<string,string>> answers,
        IReadOnlyList<string> scheduleEffects)
    {
        foreach(var id in new[]{exportId,assessmentId,assignmentId,templateId})Id(id);
        if(questions.Count!=27 || questions.Select(q=>q.Id).Distinct(StringComparer.Ordinal).Count()!=27 || answers.Count!=27)Fail("questionnaire_workbook_question_set");
        if(scheduleEffects.Count is <1 or >20||scheduleEffects.Distinct(StringComparer.Ordinal).Count()!=scheduleEffects.Count||
            scheduleEffects.Any(value=>string.IsNullOrWhiteSpace(value)||value.Length>80||value.Any(char.IsControl)))Fail("questionnaire_workbook_schedule_effects");
        using var output=new MemoryStream();
        using(var doc=SpreadsheetDocument.Create(output,SpreadsheetDocumentType.Workbook,true))
        {
            var book=doc.AddWorkbookPart();book.Workbook=new Workbook(new BookViews(new WorkbookView()));
            var styles=book.AddNewPart<WorkbookStylesPart>();styles.Stylesheet=Styles();styles.Stylesheet.Save();
            var sheets=book.Workbook.AppendChild(new Sheets());
            var responses=new SheetData();var guide=new SheetData();
            var instructions=new[]{
                "FULL SOURCE QUESTIONNAIRE — SYNTHETIC PRACTICE ONLY",
                $"Assignment: {assignmentId} | Deployment: {deploymentLabel}",
                "One deployment, 27 questions. Edit blue cells C:N. Keep IDs and exact questions unchanged. Read the Question guide for evidence and completion requirements.",
                "Statuses: unanswered, answered, unknown, blocked, unavailable, not_applicable. Partial saves are welcome; blank cells preserve the exported value.",
                "Return in the app, review competing edits, then submit separately. Reported author / attestation cells are data only: they never sign, approve, or authorize anything."
            };
            for(uint row=1;row<=5;row++)responses.Append(Row(row,[instructions[row-1]],row==1?1U:2U,34));
            responses.Append(Row(6,Headers,1,58));
            var guideInstructions=new[]{"QUESTION GUIDE — SERVER-PINNED DEFINITIONS","Read alongside Responses; this is the same versioned question set used by the web form.",
                "Evidence references only. Do not paste credentials, key material, restricted payloads, or uncontrolled URLs.",
                "Unknown / blocked / unavailable answers require rationale, next owner, date, blocker and schedule effect before submission.",
                "Responses column J — choose one exact schedule effect:\n"+
                    string.Join('\n',scheduleEffects.Chunk(2).Select(values=>string.Join(" | ",values)))+
                    "\nQuestion-specific allowed values appear below. A response is not assessment acceptance or technical verification."};
            // Explicit line breaks keep the allowed choices legible within a
            // normal viewport even though this guide's merged cells are wide.
            for(uint row=1;row<=5;row++)guide.Append(Row(row,[guideInstructions[row-1]],row==1?1U:2U,
                row==5?18*(scheduleEffects.Count+1)/2+54:30));
            guide.Append(Row(6,GuideHeaders,1,44));
            for(var index=0;index<questions.Count;index++)
            {
                var q=questions[index];Id(q.Id);if(!answers.TryGetValue(q.Id,out var answer))Fail("questionnaire_workbook_question_set");
                var number=(uint)(index+7);var row=new Row{RowIndex=number,Height=156,CustomHeight=true};
                row.Append(Cell($"A{number}",q.Id,2),Cell($"B{number}",q.Prompt,2));
                for(var f=0;f<Fields.Length;f++)row.Append(Cell($"{(char)('C'+f)}{number}",answer!.GetValueOrDefault(Fields[f],""),3));
                responses.Append(row);
                guide.Append(Row(number,[q.Id,q.Section,q.ResponseType,q.Required?"yes":"no",string.Join('\n',q.AllowedValues),q.EvidenceExpectation,q.CompletionCriteria,q.WhyItMatters],2,132));
            }
            AddSheet(book,sheets,"Responses",responses,[31,76,20,72,54,52,32,24,40,29,34,30,26,50],5,true);
            AddSheet(book,sheets,"Question guide",guide,[31,30,26,12,38,65,65,55],5,false);
            var metadata=new SheetData(Row(1,["format",Format],2,26),Row(2,["export_id",exportId],2,26),
                Row(3,["assessment_id",assessmentId],2,26),Row(4,["assignment_id",assignmentId],2,26),
                Row(5,["template_id",templateId],2,26),Row(6,["template_version",version],2,42),
                Row(7,["template_sha256",templateSha256],2,26),Row(8,["authority","Export ID is only a locator. The application owns the original snapshot and every authenticated decision."],2,45));
            AddSheet(book,sheets,"Return manifest",metadata,[28,110],0,false);
            book.Workbook.Save();if(new OpenXmlValidator().Validate(doc).Any())Fail("questionnaire_workbook_generation_invalid");
        }
        var bytes=output.ToArray();if(bytes.Length>IntakeWorkbook.MaxInputBytes)Fail("workbook_limits_exceeded");return bytes;
    }

    public static IntakeWorkbookReturn Read(byte[] bytes)
    {
        try{return ReadProfile(bytes);}
        catch(DemoValidationException){throw;}
        catch(Exception error)when(error is IOException or XmlException or FormatException or ArgumentException or OverflowException or InvalidOperationException or OpenXmlPackageException)
        {throw new DemoValidationException("questionnaire_workbook_invalid");}
    }
    private static IntakeWorkbookReturn ReadProfile(byte[] bytes)
    {
        if(bytes.Length is <4 or >IntakeWorkbook.MaxInputBytes)Fail("workbook_limits_exceeded");
        if(bytes[0]!='P'||bytes[1]!='K'||bytes[2]!=3||bytes[3]!=4)Fail("workbook_xlsx_required");
        IntakeWorkbook.Preflight(bytes); // same package, relationship, MIME, XML and expansion safety as v1
        using var stream=new MemoryStream(bytes,false);
        using var doc=SpreadsheetDocument.Open(stream,false,new OpenSettings{MaxCharactersInPart=2_097_152});
        var book=doc.WorkbookPart ?? throw new DemoValidationException("questionnaire_workbook_invalid");
        if(book.WorksheetParts.Count()!=3 || new OpenXmlValidator().Validate(doc).Any())Fail("questionnaire_workbook_profile");
        var sheets=book.Workbook?.Sheets?.Elements<Sheet>().ToArray()??[];
        if(sheets.Length!=3||sheets.Select(s=>s.Name?.Value).Distinct(StringComparer.Ordinal).Count()!=3||sheets.Select(s=>s.Id?.Value).Distinct(StringComparer.Ordinal).Count()!=3)Fail("questionnaire_workbook_profile");
        var shared=new List<string>();
        if(book.SharedStringTablePart is {} strings)
        {
            using var reader=OpenXmlReader.Create(strings);
            while(reader.Read())if(reader.ElementType==typeof(SharedStringItem)&&reader.IsStartElement)
            {
                if(shared.Count>=10000)Fail("workbook_limits_exceeded");
                var item=(SharedStringItem)reader.LoadCurrentElement()!;var text=string.Concat(item.Descendants<Text>().Select(t=>t.Text));TextLimit(text);shared.Add(text);
            }
        }
        Dictionary<string,string> Sheet(string name,int columns,int rows)
        {
            var sheet=sheets.SingleOrDefault(s=>s.Name?.Value==name);
            if(sheet?.Id?.Value is not string rid || book.GetPartById(rid) is not WorksheetPart part)throw new DemoValidationException("questionnaire_workbook_profile");
            return ReadCells(part,shared,columns,rows);
        }
        var meta=Sheet("Return manifest",2,8);var keys=new[]{"format","export_id","assessment_id","assignment_id","template_id","template_version","template_sha256","authority"};
        for(var index=0;index<keys.Length;index++)if(Get(meta,$"A{index+1}")!=keys[index])Fail("questionnaire_workbook_profile");
        if(Get(meta,"B1")!=Format)Fail("questionnaire_workbook_profile");
        var exportId=Get(meta,"B2");Id(exportId);
        var responses=Sheet("Responses",14,33);var guide=Sheet("Question guide",8,33);
        for(var i=0;i<Headers.Length;i++)if(Get(responses,$"{(char)('A'+i)}6")!=Headers[i])Fail("questionnaire_workbook_profile");
        for(var i=0;i<GuideHeaders.Length;i++)if(Get(guide,$"{(char)('A'+i)}6")!=GuideHeaders[i])Fail("questionnaire_workbook_profile");
        var result=new Dictionary<string,string>(StringComparer.Ordinal);
        var guideRows=Enumerable.Range(7,27).ToDictionary(row=>Get(guide,$"A{row}"),row=>row,StringComparer.Ordinal);
        for(var row=7;row<=33;row++)
        {
            var qid=Get(responses,$"A{row}");Id(qid);
            if(!guideRows.TryGetValue(qid,out var g))Fail("questionnaire_workbook_question_set");
            var required=Get(guide,$"D{g}");if(required is not("yes" or "no"))Fail("questionnaire_workbook_profile");
            var definition=new QuestionnaireWorkbookQuestion(qid,Get(responses,$"B{row}"),Get(guide,$"B{g}"),Get(guide,$"C{g}"),required=="yes",Get(guide,$"F{g}"),Get(guide,$"G{g}"),Get(guide,$"H{g}"),SplitLines(Get(guide,$"E{g}")));
            var fields=new Dictionary<string,string>(StringComparer.Ordinal);
            for(var index=0;index<Fields.Length;index++)fields.Add(Fields[index],Get(responses,$"{(char)('C'+index)}{row}"));
            if(!result.TryAdd(qid,JsonSerializer.Serialize(new QuestionnaireWorkbookAnswer(DefinitionHash(definition),fields,
                Get(meta,"B3"),Get(meta,"B4"),Get(meta,"B5"),Get(meta,"B6"),Get(meta,"B7")),AssessmentJson.Options)))Fail("questionnaire_workbook_question_set");
        }
        return new IntakeWorkbookReturn(exportId,result);
    }
    public static string[] SplitLines(string text)=>text.Replace("\r\n","\n",StringComparison.Ordinal).Split('\n',StringSplitOptions.RemoveEmptyEntries);
    private static Dictionary<string,string> ReadCells(WorksheetPart part,IReadOnlyList<string> shared,int columns,int maxRows)
    {
        var values=new Dictionary<string,string>(StringComparer.Ordinal);var rows=new HashSet<uint>();
        using var reader=OpenXmlReader.Create(part);
        while(reader.Read())
        {
            if(reader.ElementType!=typeof(Row)||!reader.IsStartElement)continue;
            var row=(Row)reader.LoadCurrentElement()!;var n=row.RowIndex?.Value??0;
            if(n<1||n>maxRows||!rows.Add(n)||row.ChildElements.Count>columns)Fail("questionnaire_workbook_rows");
            foreach(var child in row.ChildElements)
            {
                if(child is not Cell cell)throw new DemoValidationException("questionnaire_workbook_profile");
                var reference=cell.CellReference?.Value??"";var match=CellPattern().Match(reference);
                if(!match.Success||match.Groups[1].Value[0]-'A'>=columns||uint.Parse(match.Groups[2].Value,CultureInfo.InvariantCulture)!=n)Fail("questionnaire_workbook_rows");
                if(cell.CellFormula is not null)Fail("workbook_formula_not_allowed");
                string text;
                if(cell.DataType?.Value==CellValues.InlineString)text=string.Concat(cell.InlineString?.Descendants<Text>().Select(t=>t.Text)??[]);
                else if(cell.DataType?.Value==CellValues.SharedString)
                {
                    if(!int.TryParse(cell.CellValue?.Text,NumberStyles.None,CultureInfo.InvariantCulture,out var index)||index<0||index>=shared.Count)throw new DemoValidationException("questionnaire_workbook_invalid");
                    text=shared[index];
                }
                else if(cell.DataType is null&&cell.CellValue is null&&cell.InlineString is null)text="";
                else throw new DemoValidationException("workbook_text_cells_required");
                TextLimit(text);if(!values.TryAdd(reference,text))Fail("questionnaire_workbook_rows");
            }
        }
        return values;
    }
    private static string Get(Dictionary<string,string> values,string key)=>values.GetValueOrDefault(key,"");
    private static void Id(string value){if(!IdPattern().IsMatch(value))Fail("workbook_invalid_identifier");}
    private static void TextLimit(string value){if(value.Length>16384)Fail("workbook_limits_exceeded");try{XmlConvert.VerifyXmlChars(value);}catch(XmlException){Fail("workbook_invalid_text");}}
    private static void Fail(string code)=>throw new DemoValidationException(code);
    private static Cell Cell(string reference,string value,uint style){TextLimit(value);return new Cell{CellReference=reference,StyleIndex=style,DataType=CellValues.InlineString,InlineString=new InlineString(new Text(value){Space=SpaceProcessingModeValues.Preserve})};}
    private static Row Row(uint number,IEnumerable<string> values,uint style,double height)
    {var row=new Row{RowIndex=number,Height=height,CustomHeight=true};var col='A';foreach(var value in values)row.Append(Cell($"{col++}{number}",value,style));return row;}
    private static void AddSheet(WorkbookPart book,Sheets sheets,string name,SheetData data,double[] widths,int instructions,bool freeze)
    {
        var part=book.AddNewPart<WorksheetPart>();var view=new SheetView{WorkbookViewId=0,ShowGridLines=false};
        if(instructions>0)view.Append(new Pane{VerticalSplit=6,HorizontalSplit=freeze?2:0,TopLeftCell=freeze?"C7":"A7",ActivePane=freeze?PaneValues.BottomRight:PaneValues.BottomLeft,State=PaneStateValues.Frozen});
        var worksheet=new Worksheet(new SheetProperties(new PageSetupProperties{FitToPage=true}),new SheetViews(view),new Columns(widths.Select((w,index)=>new Column{Min=(uint)index+1,Max=(uint)index+1,Width=w,CustomWidth=true})),data);
        if(instructions>0)worksheet.Append(new MergeCells(Enumerable.Range(1,instructions).Select(row=>new MergeCell{Reference=$"A{row}:{(char)('A'+widths.Length-1)}{row}"})));
        worksheet.Append(new PageMargins{Left=.25,Right=.25,Top=.4,Bottom=.4,Header=.2,Footer=.2},new PageSetup{Orientation=OrientationValues.Landscape,FitToWidth=0,FitToHeight=0,Scale=85});
        part.Worksheet=worksheet;part.Worksheet.Save();sheets.Append(new Sheet{Id=book.GetIdOfPart(part),SheetId=(uint)sheets.ChildElements.Count+1,Name=name});
    }
    private static Stylesheet Styles()=>new(new Fonts(new Font(new FontSize{Val=11},new Color{Rgb="FF152C47"},new FontName{Val="Calibri"}),new Font(new Bold(),new FontSize{Val=11},new Color{Rgb="FFFFFFFF"},new FontName{Val="Calibri"})),
        new Fills(new Fill(new PatternFill{PatternType=PatternValues.None}),new Fill(new PatternFill{PatternType=PatternValues.Gray125}),new Fill(new PatternFill(new ForegroundColor{Rgb="FF173D60"},new BackgroundColor{Indexed=64}){PatternType=PatternValues.Solid}),new Fill(new PatternFill(new ForegroundColor{Rgb="FFE7F3FF"},new BackgroundColor{Indexed=64}){PatternType=PatternValues.Solid})),
        new Borders(new Border(new LeftBorder(),new RightBorder(),new TopBorder(),new BottomBorder(),new DiagonalBorder())),new CellStyleFormats(new CellFormat()),
        new CellFormats(new CellFormat(),Style(1,2),Style(0,0),Style(0,3)),new CellStyles(new CellStyle{Name="Normal",FormatId=0,BuiltinId=0}));
    private static CellFormat Style(uint font,uint fill)=>new(new Alignment{WrapText=true,Vertical=VerticalAlignmentValues.Top}){FontId=font,FillId=fill,ApplyFont=true,ApplyFill=true,ApplyAlignment=true,NumberFormatId=49,ApplyNumberFormat=true};
}

using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Xml;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Spreadsheet;
using DocumentFormat.OpenXml.Validation;

namespace PqcEnterpriseDemo;

public sealed record DiscoveryWorkbookAnswer(string DefinitionSha256,Dictionary<string,string> Fields,
    string AssessmentId,string RequestId,string TemplateVersion,string TemplateSha256,string FamilyId);

/// <summary>Five-question first-contact form. The workbook supplies data, never authenticated decisions.</summary>
public static partial class DiscoveryWorkbook
{
    public const string Format="pqc.discovery.return.v2";
    public const string LegacyFormat="pqc.discovery.return.v1";
    public static readonly string[] Fields=["status","text","reference","assertedBy"];
    private static readonly string[] Headers=["Question ID — keep unchanged","Question — keep unchanged","Response status","What you know / suggested route","Existing reference (optional)","Statement attributed to (optional; unverified)"];
    private static readonly string[] GuideHeaders=["Question ID","Why we ask","Recognition examples — not a product selection","A useful response"];
    [GeneratedRegex("^([A-F])([1-9][0-9]{0,2})$",RegexOptions.CultureInvariant)] private static partial Regex CellPattern();
    [GeneratedRegex("^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$",RegexOptions.CultureInvariant)] private static partial Regex IdPattern();
    public static string DefinitionHash(DiscoveryQuestion question)=>AssessmentWorkflow.Hash(question);

    public static byte[] Write(string exportId,string assessmentId,string requestId,string familyId,string familyName,string version,string templateSha256,
        IReadOnlyList<DiscoveryQuestion> questions,IReadOnlyDictionary<string,Dictionary<string,string>> answers)
    {
        foreach(var id in new[]{exportId,assessmentId,requestId,familyId})Id(id);
        if(questions.Count!=5||questions.Select(q=>q.Id).Distinct(StringComparer.Ordinal).Count()!=5||answers.Count!=5)Fail("discovery_workbook_question_set");
        using var output=new MemoryStream();
        using(var doc=SpreadsheetDocument.Create(output,SpreadsheetDocumentType.Workbook,true))
        {
            var book=doc.AddWorkbookPart();book.Workbook=new Workbook(new BookViews(new WorkbookView()));
            var styles=book.AddNewPart<WorkbookStylesPart>();styles.Stylesheet=Styles();styles.Stylesheet.Save();var sheets=book.Workbook.AppendChild(new Sheets());
            var guidance=DiscoveryWorkflow.GuidanceFor(version);
            var recognition=DiscoveryRecognition.ForFamily(familyId)??throw new DemoValidationException("discovery_recognition_missing");
            var recognitionText="PQC DISCOVERY DOMAIN: "+recognition.Domain.Name+"\nSOFTWARE CLASS: "+familyName+
                "\n"+string.Join('\n',recognition.Domain.Families.Select(f=>f.Name+": "+string.Join("; ",f.Examples.Select(e=>e.Name))))+
                "\nExamples only, not confirmed enterprise products. Full reference, product types and official sources: Software examples sheet.\n"+guidance.Introduction;
            var form=new SheetData();var instructions=new[]{
                "SOURCE DISCOVERY — FIVE QUESTIONS | SYNTHETIC PRACTICE ONLY",
                recognitionText,
                guidance.HandlingNotice,
                "Edit blue columns C:F. Status: unanswered | answered | unknown | not_my_team | referral | not_applicable. References are optional; API details and deadlines are not required.",
                "Return in the app; review and apply as a draft, then submit separately. Blank cells retain the exported value; clear in the web form. "+guidance.ReviewNotice
            };
            for(uint n=1;n<=5;n++)form.Append(Row(n,[instructions[n-1]],n==1?1U:n==2?4U:2U,n==1?28:n==2?190:48));
            form.Append(Row(6,Headers,1,42));
            var guide=new SheetData(Row(1,["format",Format],2,24),Row(2,["export_id",exportId],2,24),Row(3,["assessment_id",assessmentId],2,24),
                Row(4,["request_id",requestId],2,24),Row(5,["template_version",version],2,24),Row(6,["template_sha256",templateSha256],2,24),
                Row(7,["family_id",familyId],2,24),Row(8,["GUIDE — the same five questions as the web form; examples are recognition aids only. "+guidance.LegacyNotice],1,guidance.LegacyNotice.Length>0?68:34),Row(9,GuideHeaders,1,44));
            for(var index=0;index<5;index++)
            {
                var q=questions[index];Id(q.Id);if(!answers.TryGetValue(q.Id,out var values))Fail("discovery_workbook_question_set");
                var n=(uint)index+7;var row=new Row{RowIndex=n,Height=132,CustomHeight=true};
                row.Append(Cell($"A{n}",q.Id,2),Cell($"B{n}",q.Prompt,2));
                for(var field=0;field<Fields.Length;field++)row.Append(Cell($"{(char)('C'+field)}{n}",values!.GetValueOrDefault(Fields[field],""),3));
                form.Append(row);guide.Append(Row((uint)index+10,[q.Id,q.WhyItMatters,string.Join('\n',q.Examples),q.UsefulResponse],2,120));
            }
            AddSheet(book,sheets,"Discovery form",form,[19,44,23,52,37,37],true);
            AddSheet(book,sheets,"Guide and return",guide,[25,68,67,65],false);
            AddRecognitionSheet(book,sheets);
            book.Workbook.Save();if(new OpenXmlValidator().Validate(doc).Any())Fail("discovery_workbook_generation_invalid");
        }
        var bytes=output.ToArray();if(bytes.Length>IntakeWorkbook.MaxInputBytes)Fail("workbook_limits_exceeded");return bytes;
    }
    public static IntakeWorkbookReturn Read(byte[] bytes)
    {
        try{return ReadProfile(bytes);}
        catch(DemoValidationException){throw;}
        catch(Exception error)when(error is IOException or XmlException or FormatException or ArgumentException or OverflowException or InvalidOperationException or OpenXmlPackageException)
        {throw new DemoValidationException("discovery_workbook_invalid");}
    }
    private static IntakeWorkbookReturn ReadProfile(byte[] bytes)
    {
        if(bytes.Length is <4 or >IntakeWorkbook.MaxInputBytes)Fail("workbook_limits_exceeded");
        if(bytes[0]!='P'||bytes[1]!='K'||bytes[2]!=3||bytes[3]!=4)Fail("workbook_xlsx_required");IntakeWorkbook.Preflight(bytes);
        using var input=new MemoryStream(bytes,false);using var doc=SpreadsheetDocument.Open(input,false,new OpenSettings{MaxCharactersInPart=2_097_152});
        var book=doc.WorkbookPart??throw new DemoValidationException("discovery_workbook_invalid");
        if(book.WorksheetParts.Count() is not(2 or 3)||new OpenXmlValidator().Validate(doc).Any())Fail("discovery_workbook_profile");
        var sheets=book.Workbook?.Sheets?.Elements<Sheet>().ToArray()??[];
        if(sheets.Length!=book.WorksheetParts.Count()||sheets.Select(s=>s.Name?.Value).Distinct(StringComparer.Ordinal).Count()!=sheets.Length||sheets.Select(s=>s.Id?.Value).Distinct(StringComparer.Ordinal).Count()!=sheets.Length)Fail("discovery_workbook_profile");
        var strings=new List<string>();
        if(book.SharedStringTablePart is {} shared)
        {
            using var reader=OpenXmlReader.Create(shared);
            while(reader.Read())if(reader.ElementType==typeof(SharedStringItem)&&reader.IsStartElement)
            {
                if(strings.Count>=2500)Fail("workbook_limits_exceeded");var item=(SharedStringItem)reader.LoadCurrentElement()!;
                var text=string.Concat(item.Descendants<Text>().Select(t=>t.Text));TextLimit(text);strings.Add(text);
            }
        }
        Dictionary<string,string> Sheet(string name,int columns,int rows)
        {
            var sheet=sheets.SingleOrDefault(s=>s.Name?.Value==name);
            if(sheet?.Id?.Value is not string rid||book.GetPartById(rid) is not WorksheetPart part)throw new DemoValidationException("discovery_workbook_profile");
            return ReadCells(part,strings,columns,rows);
        }
        var form=Sheet("Discovery form",6,11);var guide=Sheet("Guide and return",4,14);
        var keys=new[]{"format","export_id","assessment_id","request_id","template_version","template_sha256","family_id"};
        for(var n=1;n<=7;n++)if(Get(guide,$"A{n}")!=keys[n-1]||Get(guide,$"C{n}")!=""||Get(guide,$"D{n}")!="")Fail("discovery_workbook_profile");
        var format=Get(guide,"B1");
        if(format==LegacyFormat){if(sheets.Length!=2)Fail("discovery_workbook_profile");}
        else if(format==Format)
        {
            if(sheets.Length!=3)Fail("discovery_workbook_profile");
            // Read-only public guidance is bounded and screened, but never becomes a returned answer,
            // installed-product claim, question-definition amendment or authenticated decision.
            var reference=Sheet("Software examples",6,850);
            if(Get(reference,"A1")!="SOFTWARE RECOGNITION REFERENCE — EXAMPLES ONLY")Fail("discovery_workbook_profile");
        }
        else Fail("discovery_workbook_profile");var export=Get(guide,"B2");Id(export);
        for(var c=0;c<Headers.Length;c++)if(Get(form,$"{(char)('A'+c)}6")!=Headers[c])Fail("discovery_workbook_profile");
        for(var c=0;c<GuideHeaders.Length;c++)if(Get(guide,$"{(char)('A'+c)}9")!=GuideHeaders[c])Fail("discovery_workbook_profile");
        var guideRows=Enumerable.Range(10,5).ToDictionary(n=>Get(guide,$"A{n}"),n=>n,StringComparer.Ordinal);var answers=new Dictionary<string,string>(StringComparer.Ordinal);
        for(var n=7;n<=11;n++)
        {
            var qid=Get(form,$"A{n}");Id(qid);if(!guideRows.TryGetValue(qid,out var g))Fail("discovery_workbook_question_set");
            var question=new DiscoveryQuestion(qid,Get(form,$"B{n}"),Get(guide,$"B{g}"),Get(guide,$"C{g}").Replace("\r\n","\n",StringComparison.Ordinal).Split('\n',StringSplitOptions.RemoveEmptyEntries).ToList(),Get(guide,$"D{g}"));
            var fields=Fields.Select((field,index)=>new KeyValuePair<string,string>(field,Get(form,$"{(char)('C'+index)}{n}"))).ToDictionary(pair=>pair.Key,pair=>pair.Value,StringComparer.Ordinal);
            var value=new DiscoveryWorkbookAnswer(DefinitionHash(question),fields,Get(guide,"B3"),Get(guide,"B4"),Get(guide,"B5"),Get(guide,"B6"),Get(guide,"B7"));
            if(!answers.TryAdd(qid,JsonSerializer.Serialize(value,AssessmentJson.Options)))Fail("discovery_workbook_question_set");
        }
        return new(export,answers);
    }
    private static Dictionary<string,string> ReadCells(WorksheetPart part,IReadOnlyList<string> shared,int columns,int maxRows)
    {
        var result=new Dictionary<string,string>(StringComparer.Ordinal);var rows=new HashSet<uint>();using var reader=OpenXmlReader.Create(part);
        while(reader.Read())
        {
            if(reader.IsStartElement&&(reader.ElementType==typeof(Formula)||reader.ElementType==typeof(Formula1)||reader.ElementType==typeof(Formula2)))Fail("workbook_formula_not_allowed");
            if(reader.ElementType!=typeof(Row)||!reader.IsStartElement)continue;var row=(Row)reader.LoadCurrentElement()!;var n=row.RowIndex?.Value??0;
            if(n<1||n>maxRows||!rows.Add(n)||row.ChildElements.Count>columns)Fail("discovery_workbook_rows");
            foreach(var child in row.ChildElements)
            {
                if(child is not Cell cell)throw new DemoValidationException("discovery_workbook_profile");var reference=cell.CellReference?.Value??"";var match=CellPattern().Match(reference);
                if(!match.Success||match.Groups[1].Value[0]-'A'>=columns||uint.Parse(match.Groups[2].Value,CultureInfo.InvariantCulture)!=n)Fail("discovery_workbook_rows");
                if(cell.CellFormula is not null)Fail("workbook_formula_not_allowed");string text;
                if(cell.DataType?.Value==CellValues.InlineString)text=string.Concat(cell.InlineString?.Descendants<Text>().Select(t=>t.Text)??[]);
                else if(cell.DataType?.Value==CellValues.SharedString)
                {if(!int.TryParse(cell.CellValue?.Text,NumberStyles.None,CultureInfo.InvariantCulture,out var i)||i<0||i>=shared.Count)throw new DemoValidationException("discovery_workbook_invalid");text=shared[i];}
                else if(cell.DataType is null&&cell.CellValue is null&&cell.InlineString is null)text="";else throw new DemoValidationException("workbook_text_cells_required");
                TextLimit(text);if(!result.TryAdd(reference,text))Fail("discovery_workbook_rows");
            }
        }
        return result;
    }
    private static string Get(Dictionary<string,string> values,string key)=>values.GetValueOrDefault(key,"");
    private static void Id(string value){if(!IdPattern().IsMatch(value))Fail("workbook_invalid_identifier");}
    private static void TextLimit(string value){if(value.Length>8192)Fail("workbook_limits_exceeded");try{XmlConvert.VerifyXmlChars(value);}catch(XmlException){Fail("workbook_invalid_text");}}
    private static void Fail(string code)=>throw new DemoValidationException(code);
    private static Cell Cell(string id,string value,uint style){TextLimit(value);return new(){CellReference=id,StyleIndex=style,DataType=CellValues.InlineString,InlineString=new InlineString(new Text(value){Space=SpaceProcessingModeValues.Preserve})};}
    private static Row Row(uint n,IEnumerable<string> values,uint style,double height){var result=new Row{RowIndex=n,Height=height,CustomHeight=true};var c='A';foreach(var value in values)result.Append(Cell($"{c++}{n}",value,style));return result;}
    private static void AddSheet(WorkbookPart book,Sheets sheets,string name,SheetData data,double[] widths,bool form)
    {
        var part=book.AddNewPart<WorksheetPart>();var view=new SheetView{WorkbookViewId=0,ShowGridLines=false};
        if(form)view.Append(new Pane{VerticalSplit=6,HorizontalSplit=2,TopLeftCell="C7",ActivePane=PaneValues.BottomRight,State=PaneStateValues.Frozen});
        var sheet=new Worksheet(new SheetProperties(new PageSetupProperties{FitToPage=true}),new SheetViews(view),new Columns(widths.Select((w,i)=>new Column{Min=(uint)i+1,Max=(uint)i+1,Width=w,CustomWidth=true})),data);
        sheet.Append(form?new MergeCells(Enumerable.Range(1,5).Select(n=>new MergeCell{Reference=$"A{n}:F{n}"})):new MergeCells(new MergeCell{Reference="A8:D8"}));
        sheet.Append(new PageMargins{Left=.25,Right=.25,Top=.4,Bottom=.4,Header=.2,Footer=.2},new PageSetup{Orientation=OrientationValues.Landscape,PaperSize=8,FitToWidth=1,FitToHeight=0});
        part.Worksheet=sheet;part.Worksheet.Save();sheets.Append(new Sheet{Id=book.GetIdOfPart(part),SheetId=(uint)sheets.ChildElements.Count+1,Name=name});
    }
    private static void AddRecognitionSheet(WorkbookPart book,Sheets sheets)
    {
        var data=new SheetData(Row(1,["SOFTWARE RECOGNITION REFERENCE — EXAMPLES ONLY"],1,28),
            Row(2,[DiscoveryRecognition.Boundary],2,72),
            Row(3,[$"Reference: {DiscoveryRecognition.Version} | reviewed {DiscoveryRecognition.ReviewedAt} | SHA-256 {DiscoveryRecognition.Sha256}. Public documentation sources below; not proof of an installed version or an approved integration."],2,44),
            Row(4,["PQC Discovery Domain","Software class","Product / service example","Offering type","Official product reference (text)","Recognition note / alias"],1,36));
        uint n=5;
        foreach(var domain in DiscoveryRecognition.Domains)
        foreach(var family in domain.Families)
        foreach(var example in family.Examples)
            data.Append(Row(n++,[domain.Name,family.Name,example.Name,example.Kind,example.Url,example.Note??""],n%2==0?2U:4U,54));
        var part=book.AddNewPart<WorksheetPart>();
        var view=new SheetView{WorkbookViewId=0,ShowGridLines=false};
        view.Append(new Pane{VerticalSplit=4,TopLeftCell="A5",ActivePane=PaneValues.BottomLeft,State=PaneStateValues.Frozen});
        var widths=new double[]{27,35,39,21,63,48};
        var sheet=new Worksheet(new SheetProperties(new PageSetupProperties{FitToPage=true}),new SheetViews(view),
            new Columns(widths.Select((w,i)=>new Column{Min=(uint)i+1,Max=(uint)i+1,Width=w,CustomWidth=true})),data,
            new MergeCells(Enumerable.Range(1,3).Select(r=>new MergeCell{Reference=$"A{r}:F{r}"})),
            new PageMargins{Left=.25,Right=.25,Top=.4,Bottom=.4,Header=.2,Footer=.2},
            new PageSetup{Orientation=OrientationValues.Landscape,PaperSize=8,FitToWidth=1,FitToHeight=0});
        part.Worksheet=sheet;part.Worksheet.Save();var index=(uint)sheets.ChildElements.Count;
        sheets.Append(new Sheet{Id=book.GetIdOfPart(part),SheetId=index+1,Name="Software examples"});
        var workbook=book.Workbook??throw new DemoValidationException("discovery_workbook_generation_invalid");
        var names=workbook.GetFirstChild<DefinedNames>()??workbook.AppendChild(new DefinedNames());
        names.Append(new DefinedName("'Software examples'!$4:$4"){Name="_xlnm.Print_Titles",LocalSheetId=index});
    }
    private static Stylesheet Styles()=>new(new Fonts(new Font(new FontSize{Val=11},new Color{Rgb="FF152C47"},new FontName{Val="Calibri"}),new Font(new Bold(),new FontSize{Val=11},new Color{Rgb="FFFFFFFF"},new FontName{Val="Calibri"})),
        new Fills(new Fill(new PatternFill{PatternType=PatternValues.None}),new Fill(new PatternFill{PatternType=PatternValues.Gray125}),new Fill(new PatternFill(new ForegroundColor{Rgb="FF173D60"},new BackgroundColor{Indexed=64}){PatternType=PatternValues.Solid}),new Fill(new PatternFill(new ForegroundColor{Rgb="FFE7F3FF"},new BackgroundColor{Indexed=64}){PatternType=PatternValues.Solid}),new Fill(new PatternFill(new ForegroundColor{Rgb="FFF0F3F7"},new BackgroundColor{Indexed=64}){PatternType=PatternValues.Solid})),
        new Borders(new Border(new LeftBorder(),new RightBorder(),new TopBorder(),new BottomBorder(),new DiagonalBorder())),new CellStyleFormats(new CellFormat()),new CellFormats(new CellFormat(),Style(1,2),Style(0,0),Style(0,3),Style(0,4)),new CellStyles(new CellStyle{Name="Normal",FormatId=0,BuiltinId=0}));
    private static CellFormat Style(uint font,uint fill)=>new(new Alignment{WrapText=true,Vertical=VerticalAlignmentValues.Top}){FontId=font,FillId=fill,ApplyFont=true,ApplyFill=true,ApplyAlignment=true,NumberFormatId=49,ApplyNumberFormat=true};
}

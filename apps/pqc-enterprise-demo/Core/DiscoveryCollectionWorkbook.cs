using System.Text.RegularExpressions;
using System.Xml;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Spreadsheet;
using DocumentFormat.OpenXml.Validation;

namespace PqcEnterpriseDemo;

/// <summary>
/// Read-only materialization of an already admitted collection and its exact exported forms.
/// This overview is deliberately not an answer-return profile or an execution authority.
/// </summary>
public static partial class DiscoveryCollectionWorkbook
{
    public const string Format="pqc.discovery.collection-overview.v1";
    private const uint Body=2,Alternate=3,Heading=1,Title=4;
    [GeneratedRegex("^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$",RegexOptions.CultureInvariant)]
    private static partial Regex Identifier();
    [GeneratedRegex("^[a-f0-9]{64}$",RegexOptions.CultureInvariant)]
    private static partial Regex Digest();

    public static byte[] Write(string assessmentId,string collectionId,string packageId,string assignedTo,
        IReadOnlyList<DiscoveryRequest> requests,IReadOnlyList<DiscoveryCollectionEntry> entries)
    {
        foreach(var id in new[]{assessmentId,collectionId,packageId,assignedTo})
            if(!Identifier().IsMatch(id))Fail("discovery_collection_identifier_invalid");
        var catalog=DiscoveryRecognition.Domains;
        var families=catalog.SelectMany(d=>d.Families.Select(f=>(Domain:d,Family:f))).ToArray();
        if(requests.Count!=27||entries.Count!=27||families.Length!=27||
            requests.Select(r=>r.FamilyId).Distinct(StringComparer.Ordinal).Count()!=27||
            requests.Select(r=>r.Id).Distinct(StringComparer.Ordinal).Count()!=27||
            entries.Select(e=>e.FamilyId).Distinct(StringComparer.Ordinal).Count()!=27||
            entries.Select(e=>e.ExportId).Distinct(StringComparer.Ordinal).Count()!=27||
            requests.Any(r=>r.AssignedTo!=assignedTo||!Identifier().IsMatch(r.Id)||
                r.Questions.Count!=5||!r.Questions.Select(q=>q.Id).SequenceEqual(Enumerable.Range(1,5).Select(n=>$"DQ-{n:00}"))||
                AssessmentWorkflow.Hash(r.Questions)!=r.TemplateSha256))
            Fail("discovery_collection_workbook_inputs_invalid");
        var byFamily=requests.ToDictionary(r=>r.FamilyId,StringComparer.Ordinal);
        var exportByFamily=entries.ToDictionary(e=>e.FamilyId,StringComparer.Ordinal);
        foreach(var (domain,family) in families)
        {
            if(!byFamily.TryGetValue(family.Id,out var request)||!exportByFamily.TryGetValue(family.Id,out var entry)||
                entry.RequestId!=request.Id||!Identifier().IsMatch(entry.ExportId)||!Digest().IsMatch(entry.Sha256)||
                entry.Filename!=$"{domain.Id}/{family.Id}.xlsx")
                Fail("discovery_collection_workbook_inputs_invalid");
        }

        using var output=new MemoryStream();
        using(var document=SpreadsheetDocument.Create(output,SpreadsheetDocumentType.Workbook,true))
        {
            var book=document.AddWorkbookPart();
            book.Workbook=new Workbook(new BookViews(new WorkbookView()));
            var styles=book.AddNewPart<WorkbookStylesPart>();styles.Stylesheet=Styles();styles.Stylesheet.Save();
            var sheets=book.Workbook.AppendChild(new Sheets());

            var start=new SheetData(
                Row(1,["PQC DISCOVERY — COMPLETE FIVE-QUESTION FORM COLLECTION"],Title,32),
                Row(2,[$"{catalog.Count} discovery domains · {requests.Count} software classes · five core questions per form · {requests.Sum(r=>r.Questions.Count)} question instances. These are not 135 different questions or a requirement to investigate every class equally."],Body,42),
                Row(3,["START HERE: choose the relevant software class below → open its individual Excel file → provide what you know → return that individual file through its assigned web request → review and apply the draft → submit separately. A useful partial answer, referral or explicit unknown is sufficient."],Alternate,58),
                Row(4,["REFERENCE ONLY — do not return this overview as a questionnaire. The All questions sheet collects the exact questions and help from the bound forms. Software examples contains the full public recognition catalog. This index has no answer-entry or approval cells."],Body,52),
                Row(5,["SYNTHETIC DEVELOPMENT COLLECTION. Do not submit credentials or sensitive files. References to existing information are optional; access, handling, standards adoption and technical verification are separate decisions. More than one product or deployment may serve the same function."],Alternate,52),
                Row(6,[$"Assessment: {assessmentId}\nCollection: {collectionId}\nPackage: {packageId}\nAssigned application principal: {assignedTo}"],Body,70),
                Row(7,[$"Overview format: {Format}. Paths are relative to the extracted ZIP. For separately attached forms, match the filename after the slash. Request/export identifiers preserve the return route; they do not confer access. Status is the export snapshot, not live progress. Existing answers and earlier exports are not replaced."],Body,52),
                Row(8,["PQC Discovery Domain","Software class","Individual form — package-relative path","Response status at export","Assigned request ID","Export identity / file checksum"],Heading,42));
            uint row=9;
            foreach(var (domain,family) in families)
            {
                var request=byFamily[family.Id];var entry=exportByFamily[family.Id];
                start.Append(Row(row++,[domain.Name,request.FamilyName,entry.Filename,request.Status,request.Id,
                    $"Export: {entry.ExportId}\nSHA-256: {entry.Sha256}\nQuestion version: {request.TemplateVersion}"],row%2==0?Body:Alternate,94));
            }
            AddSheet(book,sheets,"Start here",start,[27,37,47,20,45,62],7,8,2);

            var questions=new SheetData(
                Row(1,["ALL QUESTIONS — EXACT FIVE-QUESTION FORMS, COLLECTED IN ONE PLACE"],Title,32),
                Row(2,["Read-only overview. Each row comes from an individual form's saved question definition; this sheet does not collect answers. Why we ask, useful-response guidance and software examples are help, not additional mandatory questions. An unanswered question may remain unanswered when a useful partial response is submitted."],Body,54),
                Row(3,[$"Assessment {assessmentId} · collection {collectionId} · package {packageId}. Use the individual form identified on Start here for draft editing and return. All questions are preserved as written; this overview does not rewrite older templates."],Alternate,42),
                Row(4,["PQC Discovery Domain","Software class","Question ID","Exact question","A useful response","Why we ask","Original question examples — recognition only"],Heading,42));
            row=5;
            foreach(var (domain,family) in families)
            {
                var request=byFamily[family.Id];
                foreach(var question in request.Questions)
                    questions.Append(Row(row++,[domain.Name,request.FamilyName,question.Id,question.Prompt,
                        question.UsefulResponse,question.WhyItMatters,string.Join("; ",question.Examples)],row%2==0?Body:Alternate,
                        QuestionHeight(question)));
            }
            AddSheet(book,sheets,"All questions",questions,[22,29,12,48,47,44,40],3,4,4);

            var examples=new SheetData(
                Row(1,["SOFTWARE RECOGNITION — ALL TEN DISCOVERY DOMAINS"],Title,32),
                Row(2,[DiscoveryRecognition.Boundary],Body,68),
                Row(3,[$"Catalog: {DiscoveryRecognition.Version} · reviewed {DiscoveryRecognition.ReviewedAt} · SHA-256 {DiscoveryRecognition.Sha256}. Official references are plain text, not embedded links or instructions to connect to enterprise systems."],Alternate,48),
                Row(4,["PQC Discovery Domain","Software class","Product / service example","Offering type","Official product reference — text","Recognition note / alias"],Heading,42));
            row=5;
            foreach(var (domain,family) in families)
            foreach(var example in family.Examples)
                examples.Append(Row(row++,[domain.Name,family.Name,example.Name,example.Kind,example.Url,example.Note??""],row%2==0?Body:Alternate,
                    Math.Max(62,18*Math.Max(3,Math.Ceiling(example.Url.Length/55.0)))));
            AddSheet(book,sheets,"Software examples",examples,[27,35,39,21,63,48],3,4,4);
            book.Workbook.Save();
            if(new OpenXmlValidator().Validate(document).Any())Fail("discovery_collection_workbook_generation_invalid");
        }
        var result=output.ToArray();
        if(result.Length>IntakeWorkbook.MaxInputBytes)Fail("workbook_limits_exceeded");
        return result;
    }

    private static double QuestionHeight(DiscoveryQuestion question)=>Math.Min(300,Math.Max(110,
        18*Math.Max(Math.Ceiling(question.Prompt.Length/42.0),Math.Max(Math.Ceiling(question.UsefulResponse.Length/41.0),
        Math.Max(Math.Ceiling(question.WhyItMatters.Length/38.0),Math.Ceiling(string.Join("; ",question.Examples).Length/35.0))))+24));

    private static void AddSheet(WorkbookPart book,Sheets sheets,string name,SheetData data,double[] widths,int mergedRows,int headerRow,int frozenRows)
    {
        var part=book.AddNewPart<WorksheetPart>();var index=(uint)sheets.ChildElements.Count;
        var view=new SheetView{WorkbookViewId=0,ShowGridLines=false,ZoomScale=85};
        view.Append(new Pane{VerticalSplit=frozenRows,TopLeftCell=$"A{frozenRows+1}",ActivePane=PaneValues.BottomLeft,State=PaneStateValues.Frozen});
        var end=(char)('A'+widths.Length-1);
        var worksheet=new Worksheet(new SheetProperties(new PageSetupProperties{FitToPage=true}),new SheetViews(view),
            new Columns(widths.Select((width,i)=>new Column{Min=(uint)i+1,Max=(uint)i+1,Width=width,CustomWidth=true})),data,
            new MergeCells(Enumerable.Range(1,mergedRows).Select(n=>new MergeCell{Reference=$"A{n}:{end}{n}"})),
            new PageMargins{Left=.3,Right=.3,Top=.4,Bottom=.4,Header=.2,Footer=.2},
            new PageSetup{Orientation=OrientationValues.Landscape,PaperSize=8,FitToWidth=1,FitToHeight=0});
        part.Worksheet=worksheet;part.Worksheet.Save();
        sheets.Append(new Sheet{Id=book.GetIdOfPart(part),SheetId=index+1,Name=name});
        var workbook=book.Workbook??throw new DemoValidationException("discovery_collection_workbook_generation_invalid");
        var names=workbook.GetFirstChild<DefinedNames>()??workbook.AppendChild(new DefinedNames());
        var escaped=name.Replace("'","''",StringComparison.Ordinal);
        names.Append(new DefinedName($"'{escaped}'!${headerRow}:${headerRow}"){Name="_xlnm.Print_Titles",LocalSheetId=index});
        names.Append(new DefinedName($"'{escaped}'!$A$1:${end}${data.Elements<Row>().Max(r=>r.RowIndex!.Value)}"){Name="_xlnm.Print_Area",LocalSheetId=index});
    }

    private static Row Row(uint number,IEnumerable<string> values,uint style,double height)
    {
        var row=new Row{RowIndex=number,Height=height,CustomHeight=true};var column='A';
        foreach(var value in values)
        {
            if(value.Length>8192)Fail("workbook_limits_exceeded");
            try{XmlConvert.VerifyXmlChars(value);}catch(XmlException){Fail("workbook_invalid_text");}
            row.Append(new Cell{CellReference=$"{column++}{number}",StyleIndex=style,DataType=CellValues.InlineString,
                InlineString=new InlineString(new Text(value){Space=SpaceProcessingModeValues.Preserve})});
        }
        return row;
    }

    private static Stylesheet Styles()=>new(
        new Fonts(
            new Font(new FontSize{Val=11},new Color{Rgb="FF152C47"},new FontName{Val="Calibri"}),
            new Font(new Bold(),new FontSize{Val=11},new Color{Rgb="FFFFFFFF"},new FontName{Val="Calibri"}),
            new Font(new Bold(),new FontSize{Val=16},new Color{Rgb="FFFFFFFF"},new FontName{Val="Calibri"})),
        new Fills(new Fill(new PatternFill{PatternType=PatternValues.None}),new Fill(new PatternFill{PatternType=PatternValues.Gray125}),
            new Fill(new PatternFill(new ForegroundColor{Rgb="FF173D60"},new BackgroundColor{Indexed=64}){PatternType=PatternValues.Solid}),
            new Fill(new PatternFill(new ForegroundColor{Rgb="FFF0F4F8"},new BackgroundColor{Indexed=64}){PatternType=PatternValues.Solid})),
        new Borders(new Border(new LeftBorder(),new RightBorder(),new TopBorder(),new BottomBorder(),new DiagonalBorder())),
        new CellStyleFormats(new CellFormat()),
        new CellFormats(new CellFormat(),Style(1,2),Style(0,0),Style(0,3),Style(2,2)),
        new CellStyles(new CellStyle{Name="Normal",FormatId=0,BuiltinId=0}));
    private static CellFormat Style(uint font,uint fill)=>new(new Alignment{WrapText=true,Vertical=VerticalAlignmentValues.Top})
    {FontId=font,FillId=fill,ApplyFont=true,ApplyFill=true,ApplyAlignment=true,NumberFormatId=49,ApplyNumberFormat=true};
    private static void Fail(string code)=>throw new DemoValidationException(code);
}

using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Xml;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Spreadsheet;
using DocumentFormat.OpenXml.Validation;

namespace PqcEnterpriseDemo;

public sealed record OperationalAnswerDto(string QuestionId,string Prompt,string Status,string Text,string Reference,string Attribution,string FollowUp,string Provenance);
public sealed record OperationalProductDto(string Product,string Deployment,string Environment,string ApplicationService,string Team,string Dependencies,string Reference,string Notes,string Provenance);
public sealed record OperationalReturnDto(string Profile,string FamilyId,string TemplateVersion,string TemplateSha256,string QuestionnaireId,
    string Respondent,string Team,string KnownOwner,string ResponseDate,string Scope,string JiraKey,string CoordinatorNote,
    List<OperationalAnswerDto> Answers,List<OperationalProductDto> Products);

/// <summary>
/// Closed adapter for the already-distributed six-sheet operational edition.
/// No assessment/export identity is inferred; no supplied name is authenticated.
/// All fields are assertions for explicit coordinator association and review.
/// </summary>
public static partial class OperationalReturnWorkbook
{
    public const string Profile="pqc.discovery.email-return.v1";
    public const int MaxProducts=200;
    private static readonly string[] SheetNames=["Start here","Five questions","Products & deployments","Question help","Software examples","Version & return record"];
    private static readonly Dictionary<string,string> Statuses=new(StringComparer.OrdinalIgnoreCase)
    { ["Unanswered"]="unanswered",["Answered"]="answered",["Unknown"]="unknown",["Blocked"]="blocked",
      ["Not applicable"]="not_applicable",["Disputed"]="disputed",["Referral"]="referral",["Not my team"]="not_my_team" };
    [GeneratedRegex("^([A-H])([1-9][0-9]{0,3})$",RegexOptions.CultureInvariant)] private static partial Regex Address();
    [GeneratedRegex(@"^(\$[A-H]\$[1-9][0-9]{0,3}:\$[A-H]\$[1-9][0-9]{0,3}|\$[1-9][0-9]{0,3}:\$[1-9][0-9]{0,3})$",RegexOptions.CultureInvariant)] private static partial Regex PrintRange();
    [GeneratedRegex(@"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,7})?(Z|[+-][0-9]{2}:[0-9]{2})?$",RegexOptions.CultureInvariant)] private static partial Regex IsoDateTime();
    private static readonly Lazy<List<FormDefinition>> Definitions=new(LoadDefinitions);

    public static OperationalReturnDto Read(byte[] bytes)
    {
        try{return ReadProfile(bytes);}
        catch(DemoValidationException){throw;}
        catch(Exception e) when(e is IOException or XmlException or FormatException or ArgumentException or OverflowException or InvalidOperationException or OpenXmlPackageException or KeyNotFoundException)
        {throw new DemoValidationException("operational_workbook_invalid");}
    }
    private static OperationalReturnDto ReadProfile(byte[] bytes)
    {
        if(bytes.Length is <4 or >IntakeWorkbook.MaxInputBytes)Fail("workbook_limits_exceeded");
        if(bytes[0]!='P'||bytes[1]!='K'||bytes[2]!=3||bytes[3]!=4)Fail("workbook_xlsx_required");
        // Reuse the existing closed ZIP/XML part, relationship and expansion
        // checks. This does not alter the legacy parser's admission rules.
        IntakeWorkbook.Preflight(bytes);
        using var input=new MemoryStream(bytes,false);
        using var doc=SpreadsheetDocument.Open(input,false,new OpenSettings{MaxCharactersInPart=2_097_152});
        var book=doc.WorkbookPart??throw new DemoValidationException("operational_workbook_invalid");
        // Explicit ISO date cells (t=d) are a supported Office 2010 addition;
        // the default validator otherwise applies the Office 2007 vocabulary.
        // The SDK's semantic date validator only accepts exactly three
        // fractional digits. Validate other legitimate ISO representations
        // ourselves; every other schema or semantic error remains fatal.
        if(new OpenXmlValidator(FileFormatVersions.Office2010).Validate(doc).Any(error=>!ValidIsoDateCompatibility(error)))
            Fail("operational_workbook_profile_invalid");
        var workbook=book.Workbook??throw new DemoValidationException("operational_workbook_invalid");
        var sheets=workbook.Sheets?.Elements<Sheet>().ToArray()??[];
        if(sheets.Length!=6||book.WorksheetParts.Count()!=6||sheets.Select(s=>s.Name?.Value).Distinct(StringComparer.Ordinal).Count()!=6||
            sheets.Select(s=>s.Id?.Value).Distinct(StringComparer.Ordinal).Count()!=6||!sheets.Select(s=>s.Name?.Value??"").ToHashSet(StringComparer.Ordinal).SetEquals(SheetNames))
            Fail("operational_workbook_six_sheets_required");
        // Spreadsheet named expressions may carry executable formulas even
        // without a cell formula. Permit only inert, sheet-local print ranges.
        foreach(var name in workbook.DefinedNames?.Elements<DefinedName>()??[])
        {
            var sheetIndex=name.LocalSheetId?.Value??uint.MaxValue;
            if(name.Name?.Value is not ("_xlnm.Print_Area" or "_xlnm.Print_Titles")||name.Function?.Value==true||name.VbProcedure?.Value==true||sheetIndex>=sheets.Length)
                Fail("workbook_formula_not_allowed");
            var prefix=$"'{sheets[sheetIndex].Name!.Value}'!";
            if(!name.Text.StartsWith(prefix,StringComparison.Ordinal)||!PrintRange().IsMatch(name.Text[prefix.Length..]))Fail("workbook_formula_not_allowed");
        }
        var strings=new List<string>();
        if(book.SharedStringTablePart is {} shared)
        {
            using var reader=OpenXmlReader.Create(shared);
            while(reader.Read())if(reader.ElementType==typeof(SharedStringItem)&&reader.IsStartElement)
            {
                if(strings.Count>=10000)Fail("workbook_limits_exceeded");
                var item=(SharedStringItem)reader.LoadCurrentElement()!;
                var text=string.Concat(item.Descendants<Text>().Select(t=>t.Text));TextLimit(text);strings.Add(text);
            }
        }
        var parsed=new Dictionary<string,Dictionary<string,RawCell>>(StringComparer.Ordinal);
        foreach(var sheet in sheets)
        {
            if(sheet.Id?.Value is not string id||book.GetPartById(id) is not WorksheetPart part)Fail("operational_workbook_profile_invalid");
            part=(WorksheetPart)book.GetPartById(sheet.Id!.Value!);
            var worksheet=part.Worksheet??throw new DemoValidationException("operational_workbook_invalid");
            foreach(var validation in worksheet.Descendants<DataValidation>())
            {
                // Excel's literal dropdown list is safe data, not a cell formula.
                var formula=validation.Formula1?.Text??"";
                // LibreOffice's Excel writer also emits an inert formula2=0
                // placeholder for lists. It is not evaluated or generalized.
                if(validation.Type?.Value!=DataValidationValues.List||(validation.Formula2 is {} second&&second.Text!="0")||formula.Length<2||formula[0]!='"'||formula[^1]!='"'||
                    formula[1..^1].Split(',').Any(s=>!Statuses.ContainsKey(s)))Fail("operational_workbook_validation_formula_rejected");
            }
            if(worksheet.Descendants<Formula>().Any()||worksheet.Descendants<Formula2>().Any(f=>!f.Ancestors<DataValidation>().Any())||
                worksheet.Descendants<Formula1>().Any(f=>!f.Ancestors<DataValidation>().Any()))Fail("workbook_formula_not_allowed");
            parsed.Add(sheet.Name!.Value!,ReadCells(worksheet,strings));
        }
        string Get(string sheet,string address)=>parsed[sheet].GetValueOrDefault(address)?.Text??"";
        if(Get("Version & return record","D9")!=Profile)Fail("operational_workbook_edition_unsupported");
        var questionnaire=Get("Version & return record","D3");
        var definition=Definitions.Value.SingleOrDefault(d=>d.QuestionnaireId==questionnaire)
            ??throw new DemoValidationException("operational_workbook_questionnaire_unknown");
        if(definition.DeliveryEdition!=Profile||definition.TemplateVersion!="pqc.discovery.v2")Fail("operational_workbook_definition_invalid");
        var allowed=new Dictionary<string,HashSet<string>>(StringComparer.Ordinal);
        foreach(var name in SheetNames)allowed[name]=definition.ReadonlyCells[name].Keys.ToHashSet(StringComparer.Ordinal);
        foreach(var address in definition.RespondentCells.Values)allowed["Start here"].Add(address);
        allowed["Version & return record"].Add(definition.CoordinatorCell);
        foreach(var q in definition.Questions)
            foreach(var address in new[]{q.Status,q.Text,q.Reference,q.Attribution,q.FollowUp})allowed["Five questions"].Add(address);
        foreach(var name in SheetNames)
        {
            foreach(var expected in definition.ReadonlyCells[name])
            {
                // Product continuation rows may move the footer down. All
                // headers remain fixed, and exactly one footer must survive.
                if(name=="Products & deployments"&&expected.Key=="A11")continue;
                if(Get(name,expected.Key)!=expected.Value)Fail("operational_workbook_definition_changed");
            }
            if(name=="Products & deployments")continue;
            foreach(var cell in parsed[name])
                if(cell.Value.Text.Length>0&&!allowed[name].Contains(cell.Key))Fail("operational_workbook_unrecognized_answer_cell");
        }
        var answers=new List<OperationalAnswerDto>();
        foreach(var q in definition.Questions)
        {
            var status=Get("Five questions",q.Status).Trim();
            if(status.Length==0)status="Unanswered";
            if(!Statuses.TryGetValue(status,out var normalized))Fail("operational_workbook_status_invalid");
            answers.Add(new(q.Id,q.Prompt,normalized!,Get("Five questions",q.Text),Get("Five questions",q.Reference),
                Get("Five questions",q.Attribution),Get("Five questions",q.FollowUp),
                $"Five questions!{q.PromptCell},{q.Status},{q.Text},{q.Reference},{q.Attribution},{q.FollowUp}"));
        }
        var products=new List<OperationalProductDto>();var footerCount=0;
        foreach(var row in parsed["Products & deployments"].GroupBy(c=>int.Parse(c.Key[1..],CultureInfo.InvariantCulture)).OrderBy(g=>g.Key))
        {
            if(row.Key<4)continue;
            var values=Enumerable.Range(0,8).Select(c=>Get("Products & deployments",$"{(char)('A'+c)}{row.Key}")).ToArray();
            if(values.All(string.IsNullOrWhiteSpace))continue;
            if(values[0]==definition.ProductFooter)
            {
                if(values.Skip(1).Any(v=>v.Length>0))Fail("operational_workbook_footer_changed");
                footerCount++;continue;
            }
            if(products.Count>=MaxProducts)Fail("operational_workbook_product_limit");
            products.Add(new(values[0],values[1],values[2],values[3],values[4],values[5],values[6],values[7],$"Products & deployments!A{row.Key}:H{row.Key}"));
        }
        if(footerCount!=1)Fail("operational_workbook_footer_changed");
        string Respondent(string key)=>Get("Start here",definition.RespondentCells[key]);
        var dateCell=parsed["Start here"].GetValueOrDefault(definition.RespondentCells["responseDate"]);
        var date=dateCell?.Text??"";
        if(dateCell?.Kind==CellValues.Number&&date.Length>0)
        {
            if(!double.TryParse(date,NumberStyles.Float,CultureInfo.InvariantCulture,out var serial)||!double.IsFinite(serial)||serial<1||serial>2950000)Fail("operational_workbook_date_invalid");
            // Preserve the civil date, respecting the workbook's epoch. Excel's
            // fictional 1900-02-29 is rejected rather than silently changed.
            var epoch1904=workbook.WorkbookProperties?.Date1904?.Value==true;
            if(!epoch1904&&serial==60)Fail("operational_workbook_date_invalid");
            date=(epoch1904?new DateTime(1904,1,1).AddDays(serial):DateTime.FromOADate(serial<60?serial+1:serial)).ToString("yyyy-MM-dd",CultureInfo.InvariantCulture);
        }
        else if(dateCell?.Kind==CellValues.Date&&date.Length>0)
        {
            if(!DateTime.TryParse(date,CultureInfo.InvariantCulture,DateTimeStyles.RoundtripKind,out var value))Fail("operational_workbook_date_invalid");
            date=value.ToString("yyyy-MM-dd",CultureInfo.InvariantCulture);
        }
        var result=new OperationalReturnDto(Profile,definition.FamilyId,definition.TemplateVersion,definition.TemplateSha256,definition.QuestionnaireId,
            Respondent("respondent"),Respondent("intendedTeam"),Respondent("owner"),date,Respondent("scope"),Respondent("jiraIssueKey"),Get("Version & return record",definition.CoordinatorCell),answers,products);
        if(JsonSerializer.SerializeToUtf8Bytes(result,AssessmentJson.Options).Length>524288)Fail("operational_workbook_response_limit");
        return result;
    }

    private sealed record RawCell(string Text,CellValues Kind);
    private static Dictionary<string,RawCell> ReadCells(Worksheet worksheet,IReadOnlyList<string> strings)
    {
        var result=new Dictionary<string,RawCell>(StringComparer.Ordinal);var rows=new HashSet<uint>();var total=0;
        foreach(var row in worksheet.GetFirstChild<SheetData>()?.Elements<Row>()??[])
        {
            var rowIndex=row.RowIndex?.Value??0;
            if(rowIndex is <1 or >1200||!rows.Add(rowIndex)||row.ChildElements.Count>8)Fail("operational_workbook_rows_invalid");
            foreach(var child in row.ChildElements)
            {
                if(child is not Cell cell)Fail("operational_workbook_cell_invalid");
                cell=(Cell)child;var reference=cell.CellReference?.Value??"";var match=Address().Match(reference);
                if(!match.Success||uint.Parse(match.Groups[2].Value,CultureInfo.InvariantCulture)!=rowIndex||cell.CellFormula is not null)Fail("operational_workbook_cell_invalid");
                string text;var kind=cell.DataType?.Value??CellValues.Number;
                if(kind==CellValues.InlineString)text=string.Concat(cell.InlineString?.Descendants<Text>().Select(t=>t.Text)??[]);
                else if(kind==CellValues.SharedString)
                {
                    if(!int.TryParse(cell.CellValue?.Text,NumberStyles.None,CultureInfo.InvariantCulture,out var index)||index<0||index>=strings.Count)Fail("operational_workbook_string_invalid");
                    text=strings[index];
                }
                else if(kind==CellValues.Number||kind==CellValues.Date)text=cell.CellValue?.Text??"";
                else throw new DemoValidationException("operational_workbook_cell_type_unsupported");
                TextLimit(text);total+=text.Length;if(total>262144)Fail("workbook_limits_exceeded");
                if(!result.TryAdd(reference,new(text,kind)))Fail("operational_workbook_duplicate_cell");
            }
        }
        return result;
    }
    private static List<FormDefinition> LoadDefinitions()
    {
        using var stream=typeof(OperationalReturnWorkbook).Assembly.GetManifestResourceStream("PqcEnterpriseDemo.OperationalReturn.v1")
            ??throw new DemoStoreException("operational_definitions_missing");
        var catalog=JsonSerializer.Deserialize<DefinitionCatalog>(stream,AssessmentJson.Options)??throw new DemoStoreException("operational_definitions_invalid");
        if(catalog.SchemaVersion!="pqc.operational-return-compatibility.v1"||catalog.Forms.Count!=27||catalog.Forms.Select(f=>f.FamilyId).Distinct(StringComparer.Ordinal).Count()!=27||
            catalog.Forms.Any(f=>f.Questions.Count!=5||!f.Questions.Select(q=>q.Id).SequenceEqual(Enumerable.Range(1,5).Select(i=>$"DQ-{i:00}"))))
            throw new DemoStoreException("operational_definitions_invalid");
        return catalog.Forms;
    }
    private static void TextLimit(string text){if(text.Length>8192)Fail("workbook_limits_exceeded");XmlConvert.VerifyXmlChars(text);}
    private static bool ValidIsoDateCompatibility(ValidationErrorInfo error)
    {
        var cell=error.Node as Cell??error.Node?.Parent as Cell;
        return error.Id=="Sem_CellValue"&&cell?.DataType?.Value==CellValues.Date&&cell.CellValue is {} value&&
            IsoDateTime().IsMatch(value.Text)&&DateTime.TryParse(value.Text,CultureInfo.InvariantCulture,DateTimeStyles.RoundtripKind,out _);
    }
    private static void Fail(string code)=>throw new DemoValidationException(code);
    private sealed record DefinitionCatalog(string SchemaVersion,List<FormDefinition> Forms);
    private sealed record FormDefinition(string FamilyId,string DomainId,string QuestionnaireId,string WorkItemId,string TemplateVersion,string TemplateSha256,
        string SourceWorkbookSha256,string DeliveryEdition,Dictionary<string,string> RespondentCells,List<QuestionDefinition> Questions,
        string CoordinatorCell,Dictionary<string,Dictionary<string,string>> ReadonlyCells,string ProductFooter);
    private sealed record QuestionDefinition(string Id,string Prompt,string PromptCell,string Status,string Text,string Reference,string Attribution,string FollowUp);
}

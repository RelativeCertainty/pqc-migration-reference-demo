using System.Globalization;
using System.IO.Compression;
using System.Text.RegularExpressions;
using System.Xml;
using System.Xml.Linq;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Spreadsheet;
using DocumentFormat.OpenXml.Validation;

namespace PqcEnterpriseDemo;

/// <summary>The export ID is only an untrusted locator for a server-held snapshot.</summary>
public sealed record IntakeWorkbookReturn(string ExportId, Dictionary<string, string> Answers);

/// <summary>
/// Closed questionnaire profile, not a general Excel importer. Run Read in the
/// bounded parser process, never inside the request's database transaction.
/// No credentials, external resolution, filesystem extraction, or payload logs.
/// </summary>
public static partial class IntakeWorkbook
{
    public const int MaxInputBytes = 1_048_576;
    public const int MaxAnswers = 500;
    public const string Format = "pqc.intake.return.v1";
    private const long MaxExpandedBytes = 64L * 1024 * 1024;
    private const int MaxPartBytes = 8 * 1024 * 1024;
    private const long MaxXmlCharacters = 2 * 1024 * 1024;
    private const string SpreadsheetNs = "http://schemas.openxmlformats.org/spreadsheetml/2006/main";
    private const string RelationshipNs = "http://schemas.openxmlformats.org/package/2006/relationships";
    private const string OfficeRelationshipNs = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
    private static readonly string[] Headers = ["Record ID", "Question or purpose", "Your answer (text)"];
    private static readonly string[] Instructions = [
        "Discovery and Evidence Intake — synthetic practice",
        "SYNTHETIC ONLY — no enterprise acceptance or technical verification.",
        "Fill blue cells in column C. Keep row IDs unchanged; partial responses are welcome.",
        "Return through the original request. Blank answers do not clear existing values; clear explicitly in the app.",
        "Unknown? Enter 'I do not know' or suggest a better source. The coordinator decides the next handoff."
    ];

    [GeneratedRegex("^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$", RegexOptions.CultureInvariant)]
    private static partial Regex IdentifierPattern();
    [GeneratedRegex("^xl/worksheets/sheet[1-9][0-9]*\\.xml$", RegexOptions.CultureInvariant)]
    private static partial Regex SheetPathPattern();
    [GeneratedRegex("^xl/theme/theme[1-9][0-9]*\\.xml$", RegexOptions.CultureInvariant)]
    private static partial Regex ThemePathPattern();
    [GeneratedRegex("^([A-C])([1-9][0-9]{0,5})$", RegexOptions.CultureInvariant)]
    private static partial Regex CellReferencePattern();
    [GeneratedRegex("^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$", RegexOptions.CultureInvariant)]
    private static partial Regex ExtensionPattern();
    [GeneratedRegex("^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,79}/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,159}$", RegexOptions.CultureInvariant)]
    private static partial Regex MimePattern();

    public static byte[] Write(string exportId, string assessmentId, string requestId,
        IReadOnlyDictionary<string, string> answers, IReadOnlyDictionary<string, string> rowLabels)
    {
        RequireId(exportId); RequireId(assessmentId); RequireId(requestId);
        if (answers.Count is 0 or > MaxAnswers || answers.Count != rowLabels.Count ||
            answers.Keys.Any(key => !rowLabels.ContainsKey(key))) Fail("workbook_invalid_rows");
        foreach (var (key, value) in answers)
        {
            RequireId(key); RequireText(value, 4096); RequireText(rowLabels[key], 2048);
            if (string.IsNullOrWhiteSpace(rowLabels[key])) Fail("workbook_invalid_rows");
        }
        using var output = new MemoryStream();
        using (var document = SpreadsheetDocument.Create(output, SpreadsheetDocumentType.Workbook, true))
        {
            var workbook = document.AddWorkbookPart();
            workbook.Workbook = new Workbook(new BookViews(new WorkbookView()));
            var styles = workbook.AddNewPart<WorkbookStylesPart>();
            styles.Stylesheet = Styles();
            styles.Stylesheet.Save();
            var sheets = workbook.Workbook.AppendChild(new Sheets());
            var responses = workbook.AddNewPart<WorksheetPart>();
            var data = new SheetData();
            for (uint index = 0; index < Instructions.Length; index++)
                data.Append(MakeRow(index + 1, [Instructions[index]], index == 0 ? 1U : 2U, 32));
            data.Append(MakeRow(6, Headers, 1, 30));
            uint rowNumber = 7;
            foreach (var (key, answer) in answers)
            {
                // Long responses remain readable in the editable sheet; Excel's
                // own maximum row height still applies for unusually long text.
                var lines = Math.Max(3, Math.Max((rowLabels[key].Length + 59) / 60, (answer.Length + 64) / 65));
                var row = new Row { RowIndex = rowNumber, Height = Math.Min(400, 18 * lines + 12), CustomHeight = true };
                row.Append(TextCell($"A{rowNumber}", key, 2), TextCell($"B{rowNumber}", rowLabels[key], 2), TextCell($"C{rowNumber}", answer, 3));
                data.Append(row); rowNumber++;
            }
            var view = new SheetView { WorkbookViewId = 0, ShowGridLines = false };
            view.Append(new Pane { VerticalSplit = 6, TopLeftCell = "A7", ActivePane = PaneValues.BottomLeft, State = PaneStateValues.Frozen });
            responses.Worksheet = new Worksheet(new SheetProperties(new PageSetupProperties { FitToPage = true }), new SheetViews(view),
                new Columns(new Column { Min = 1, Max = 1, Width = 36, CustomWidth = true },
                    new Column { Min = 2, Max = 2, Width = 65, CustomWidth = true },
                    new Column { Min = 3, Max = 3, Width = 70, CustomWidth = true }), data,
                new MergeCells(Enumerable.Range(1, 5).Select(row => new MergeCell { Reference = $"A{row}:C{row}" })),
                new PageMargins { Left = 0.25, Right = 0.25, Top = 0.4, Bottom = 0.4, Header = 0.2, Footer = 0.2 },
                new PageSetup { Orientation = OrientationValues.Landscape, FitToWidth = 1, FitToHeight = 0 });
            if (responses.Worksheet.OuterXml.Length > MaxXmlCharacters) Fail("workbook_limits_exceeded");
            responses.Worksheet.Save();
            sheets.Append(new Sheet { Id = workbook.GetIdOfPart(responses), SheetId = 1, Name = "Responses" });
            var manifest = workbook.AddNewPart<WorksheetPart>();
            var metadata = new SheetData(MakeRow(1, ["format", Format], 2, 24),
                MakeRow(2, ["export_id", exportId], 2, 24), MakeRow(3, ["assessment_id", assessmentId], 2, 24),
                MakeRow(4, ["request_id", requestId], 2, 24),
                MakeRow(5, ["notice", "Return locator only; workbook metadata does not grant access or record approval."], 2, 45));
            manifest.Worksheet = new Worksheet(new Columns(new Column { Min = 1, Max = 1, Width = 24, CustomWidth = true },
                new Column { Min = 2, Max = 2, Width = 100, CustomWidth = true }), metadata);
            manifest.Worksheet.Save();
            sheets.Append(new Sheet { Id = workbook.GetIdOfPart(manifest), SheetId = 2, Name = "Return manifest" });
            workbook.Workbook.Save();
            if (new OpenXmlValidator().Validate(document).Any()) Fail("workbook_generation_invalid");
        }
        var bytes = output.ToArray();
        if (bytes.Length > MaxInputBytes) Fail("workbook_limits_exceeded");
        return bytes;
    }

    public static IntakeWorkbookReturn Read(byte[] bytes)
    {
        try { return ReadProfile(bytes); }
        catch (DemoValidationException) { throw; }
        catch (Exception error) when (error is InvalidDataException or IOException or XmlException or
            FormatException or ArgumentException or OverflowException or InvalidOperationException or OpenXmlPackageException)
        { throw new DemoValidationException("workbook_invalid"); }
    }

    private static IntakeWorkbookReturn ReadProfile(byte[] bytes)
    {
        if (bytes.Length is < 4 or > MaxInputBytes) Fail("workbook_limits_exceeded");
        if (bytes[0] != 'P' || bytes[1] != 'K' || bytes[2] != 3 || bytes[3] != 4) Fail("workbook_xlsx_required");
        Preflight(bytes);
        using var stream = new MemoryStream(bytes, false);
        using var document = SpreadsheetDocument.Open(stream, false, new OpenSettings { MaxCharactersInPart = MaxXmlCharacters });
        var workbook = document.WorkbookPart ?? throw new DemoValidationException("workbook_invalid");
        if (workbook.WorksheetParts.Count() != 2) Fail("workbook_unsupported_profile");
        if (new OpenXmlValidator().Validate(document).Any()) Fail("workbook_invalid_schema");
        var workbookRoot = workbook.Workbook ?? throw new DemoValidationException("workbook_invalid");
        var sheets = workbookRoot.Sheets?.Elements<Sheet>().ToArray() ?? [];
        if (sheets.Length != 2 || sheets.Select(sheet => sheet.Name?.Value).Distinct(StringComparer.Ordinal).Count() != 2)
            Fail("workbook_unsupported_profile");
        var responses = sheets.SingleOrDefault(sheet => sheet.Name?.Value == "Responses");
        var manifest = sheets.SingleOrDefault(sheet => sheet.Name?.Value == "Return manifest");
        if (responses?.Id?.Value is not string responseId || manifest?.Id?.Value is not string manifestId)
            throw new DemoValidationException("workbook_unsupported_profile");
        if (responseId == manifestId) Fail("workbook_invalid");
        if (workbook.GetPartById(responseId) is not WorksheetPart responsePart || workbook.GetPartById(manifestId) is not WorksheetPart manifestPart)
            throw new DemoValidationException("workbook_invalid");
        var sharedStrings = ReadSharedStrings(workbook.SharedStringTablePart);
        var metadata = ReadCells(manifestPart, sharedStrings, 5);
        if (Get(metadata, "A1") != "format" || Get(metadata, "B1") != Format ||
            Get(metadata, "A2") != "export_id" || Get(metadata, "A3") != "assessment_id" ||
            Get(metadata, "A4") != "request_id" || Get(metadata, "A5") != "notice" ||
            metadata.Keys.Any(key => key.StartsWith('C'))) Fail("workbook_unsupported_profile");
        var exportId = Get(metadata, "B2"); RequireId(exportId);
        RequireId(Get(metadata, "B3")); RequireId(Get(metadata, "B4"));
        var cells = ReadCells(responsePart, sharedStrings, MaxAnswers + 6);
        for (var index = 0; index < Headers.Length; index++)
            if (Get(cells, $"{(char)('A' + index)}6") != Headers[index]) Fail("workbook_unsupported_profile");
        var answers = new Dictionary<string, string>(StringComparer.Ordinal);
        var dataRows = cells.Keys.Select(key => int.Parse(key[1..], CultureInfo.InvariantCulture)).Where(row => row > 6).Distinct().Order().ToArray();
        foreach (var row in dataRows)
        {
            var key = Get(cells, $"A{row}");
            var label = Get(cells, $"B{row}");
            var answer = Get(cells, $"C{row}");
            if (key.Length == 0 && label.Length == 0 && answer.Length == 0) continue;
            RequireId(key); RequireText(label, 2048);
            if (string.IsNullOrWhiteSpace(label) || !answers.TryAdd(key, answer)) Fail("workbook_invalid_rows");
        }
        if (answers.Count is 0 or > MaxAnswers) Fail("workbook_invalid_rows");
        return new IntakeWorkbookReturn(exportId, answers);
    }

    private static Dictionary<string, string> ReadCells(WorksheetPart part, IReadOnlyList<string> sharedStrings, int maxRows)
    {
        var result = new Dictionary<string, string>(StringComparer.Ordinal);
        var rowIds = new HashSet<uint>();
        using var reader = OpenXmlReader.Create(part);
        while (reader.Read())
        {
            if (reader.ElementType != typeof(Row) || !reader.IsStartElement) continue;
            var row = (Row)reader.LoadCurrentElement()!;
            var number = row.RowIndex?.Value ?? 0;
            if (number is 0 || number > maxRows || !rowIds.Add(number) || row.ChildElements.Count > 3) Fail("workbook_invalid_rows");
            foreach (var child in row.ChildElements)
            {
                if (child is not Cell cell) throw new DemoValidationException("workbook_unsupported_profile");
                var reference = cell.CellReference?.Value ?? "";
                var match = CellReferencePattern().Match(reference);
                if (!match.Success || uint.Parse(match.Groups[2].Value, CultureInfo.InvariantCulture) != number)
                    Fail("workbook_invalid_rows");
                var text = ReadCell(cell, sharedStrings);
                if (!result.TryAdd(reference, text)) Fail("workbook_invalid_rows");
            }
        }
        return result;
    }

    private static string ReadCell(Cell cell, IReadOnlyList<string> sharedStrings)
    {
        if (cell.CellFormula is not null || cell.Descendants<CellFormula>().Any()) Fail("workbook_formula_not_allowed");
        string result;
        if (cell.DataType?.Value == CellValues.InlineString)
            result = string.Concat(cell.InlineString?.Descendants<Text>().Select(text => text.Text) ?? []);
        else if (cell.DataType?.Value == CellValues.SharedString)
        {
            if (!int.TryParse(cell.CellValue?.Text, NumberStyles.None, CultureInfo.InvariantCulture, out var index) ||
                index < 0 || index >= sharedStrings.Count) throw new DemoValidationException("workbook_invalid");
            result = sharedStrings[index];
        }
        else if (cell.DataType is null && cell.CellValue is null && cell.InlineString is null) result = "";
        else throw new DemoValidationException("workbook_text_cells_required");
        RequireText(result, 4096);
        return result;
    }

    private static List<string> ReadSharedStrings(SharedStringTablePart? part)
    {
        var result = new List<string>();
        if (part is null) return result;
        using var reader = OpenXmlReader.Create(part);
        while (reader.Read())
        {
            if (reader.ElementType != typeof(SharedStringItem) || !reader.IsStartElement) continue;
            if (result.Count >= 10_000) Fail("workbook_limits_exceeded");
            var item = (SharedStringItem)reader.LoadCurrentElement()!;
            var text = string.Concat(item.Descendants<Text>().Select(value => value.Text));
            RequireText(text, 4096); result.Add(text);
        }
        return result;
    }

    internal static void Preflight(byte[] bytes)
    {
        using var stream = new MemoryStream(bytes, false);
        using var zip = new ZipArchive(stream, ZipArchiveMode.Read, true);
        if (zip.Entries.Count is < 5 or > 64) Fail("workbook_limits_exceeded");
        var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var entry in zip.Entries)
        {
            if (!AllowedPart(entry.FullName) || !names.Add(entry.FullName)) Fail("workbook_unsupported_package");
            if (entry.Length > MaxPartBytes) Fail("workbook_limits_exceeded");
        }
        if (!names.Contains("[Content_Types].xml") || !names.Contains("_rels/.rels") ||
            !names.Contains("xl/workbook.xml") || !names.Contains("xl/_rels/workbook.xml.rels")) Fail("workbook_invalid");
        long expanded = 0;
        foreach (var entry in zip.Entries)
        {
            using var source = entry.Open();
            using var buffer = new MemoryStream();
            var chunk = new byte[16_384];
            int count;
            while ((count = source.Read(chunk)) != 0)
            {
                expanded += count;
                if (expanded > MaxExpandedBytes || buffer.Length + count > MaxPartBytes) Fail("workbook_limits_exceeded");
                buffer.Write(chunk, 0, count);
            }
            buffer.Position = 0;
            using (var reader = XmlReader.Create(buffer, XmlSettings()))
            {
                while (reader.Read())
                {
                    if (reader.Depth > 32 || reader.AttributeCount > 64) Fail("workbook_limits_exceeded");
                    if (reader.NodeType != XmlNodeType.Element) continue;
                    if (reader.NamespaceURI == SpreadsheetNs && reader.LocalName == "f") Fail("workbook_formula_not_allowed");
                    if (reader.LocalName is "oleObject" or "externalReference" or "connection" or "hyperlink") Fail("workbook_unsupported_package");
                }
            }
            if (entry.FullName.EndsWith(".rels", StringComparison.Ordinal))
            {
                buffer.Position = 0;
                using var reader = XmlReader.Create(buffer, XmlSettings());
                ValidateRelationships(XDocument.Load(reader), entry.FullName, names);
            }
            if (entry.FullName == "[Content_Types].xml")
            {
                buffer.Position = 0;
                using var reader = XmlReader.Create(buffer, XmlSettings());
                ValidateContentTypes(XDocument.Load(reader), names);
            }
        }
    }

    private static bool AllowedPart(string path) => path is "[Content_Types].xml" or "_rels/.rels" or
        "xl/workbook.xml" or "xl/_rels/workbook.xml.rels" or "xl/styles.xml" or "xl/sharedStrings.xml" or
        "docProps/core.xml" or "docProps/app.xml" or "docProps/custom.xml" || SheetPathPattern().IsMatch(path) || ThemePathPattern().IsMatch(path);

    private static void ValidateRelationships(XDocument document, string path, HashSet<string> names)
    {
        XNamespace ns = RelationshipNs;
        if (document.Root?.Name != ns + "Relationships") Fail("workbook_invalid");
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var relationship in document.Root!.Elements())
        {
            if (relationship.Name != ns + "Relationship") Fail("workbook_invalid");
            var id = (string?)relationship.Attribute("Id") ?? "";
            var target = (string?)relationship.Attribute("Target") ?? "";
            var type = (string?)relationship.Attribute("Type") ?? "";
            var mode = (string?)relationship.Attribute("TargetMode");
            if (id.Length == 0 || !ids.Add(id) || mode is not (null or "Internal") ||
                target.Length == 0 || target.Contains(':') || target.Contains('\\') || target.Contains('%') || target.Contains('#') || target.Contains('?'))
                Fail("workbook_unsupported_package");
            var resolved = target.StartsWith('/') ? target[1..] : (path.StartsWith("xl/", StringComparison.Ordinal) ? "xl/" : "") + target;
            if (!AllowedPart(resolved) || !names.Contains(resolved)) Fail("workbook_unsupported_package");
            if (type != "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" &&
                type != OfficeRelationshipNs + "/officeDocument" && type != OfficeRelationshipNs + "/worksheet" &&
                type != OfficeRelationshipNs + "/styles" && type != OfficeRelationshipNs + "/sharedStrings" &&
                type != OfficeRelationshipNs + "/theme" && type != OfficeRelationshipNs + "/extended-properties" &&
                type != OfficeRelationshipNs + "/custom-properties") Fail("workbook_unsupported_package");
        }
    }

    private static void ValidateContentTypes(XDocument document, HashSet<string> names)
    {
        XNamespace ns = "http://schemas.openxmlformats.org/package/2006/content-types";
        if (document.Root?.Name != ns + "Types") Fail("workbook_invalid");
        var identities = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var defaults = new Dictionary<string, string>(StringComparer.Ordinal);
        var overrides = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var element in document.Root!.Elements())
        {
            var contentType = (string?)element.Attribute("ContentType") ?? "";
            var isDefault = element.Name == ns + "Default";
            if (!isDefault && element.Name != ns + "Override") Fail("workbook_invalid");
            var identity = (string?)element.Attribute(isDefault ? "Extension" : "PartName") ?? "";
            if (identity.Length == 0 || !identities.Add((isDefault ? "extension:" : "part:") + identity)) Fail("workbook_invalid");
            if (isDefault)
            {
                // Office applications may emit unused image/font defaults.
                // A declaration is not an admitted payload part: every actual
                // ZIP entry still has to pass the closed path allowlist and
                // exact effective MIME comparison below. Never load or fetch
                // anything merely because it is declared here.
                if (!ExtensionPattern().IsMatch(identity) || !MimePattern().IsMatch(contentType) ||
                    element.Attributes().Count(attribute => !attribute.IsNamespaceDeclaration) != 2 || element.HasElements)
                    Fail("workbook_invalid");
                defaults.Add(identity, contentType);
            }
            else
            {
                if (!identity.StartsWith('/') || !AllowedPart(identity[1..]) || !XmlContentType(contentType)) Fail("workbook_unsupported_package");
                overrides.Add(identity[1..], contentType);
            }
        }
        // The SDK legitimately makes the workbook MIME type the xml default.
        // Validate each part's effective type instead of assuming application/xml.
        foreach (var name in names.Where(name => name != "[Content_Types].xml"))
        {
            var extension = name[(name.LastIndexOf('.') + 1)..];
            var actual = overrides.GetValueOrDefault(name, defaults.GetValueOrDefault(extension, ""));
            var expected = name switch
            {
                "_rels/.rels" or "xl/_rels/workbook.xml.rels" => "application/vnd.openxmlformats-package.relationships+xml",
                "xl/workbook.xml" => "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
                "xl/styles.xml" => "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml",
                "xl/sharedStrings.xml" => "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml",
                "docProps/core.xml" => "application/vnd.openxmlformats-package.core-properties+xml",
                "docProps/app.xml" => "application/vnd.openxmlformats-officedocument.extended-properties+xml",
                "docProps/custom.xml" => "application/vnd.openxmlformats-officedocument.custom-properties+xml",
                _ when SheetPathPattern().IsMatch(name) => "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
                _ when ThemePathPattern().IsMatch(name) => "application/vnd.openxmlformats-officedocument.theme+xml",
                _ => ""
            };
            if (actual != expected || expected.Length == 0) Fail("workbook_unsupported_package");
        }
    }
    private static bool XmlContentType(string contentType) => contentType is
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml" or
                "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml" or
                "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml" or
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml" or
                "application/vnd.openxmlformats-officedocument.theme+xml" or
                "application/vnd.openxmlformats-package.core-properties+xml" or
                "application/vnd.openxmlformats-officedocument.extended-properties+xml" or
                "application/vnd.openxmlformats-officedocument.custom-properties+xml";

    private static XmlReaderSettings XmlSettings() => new() { DtdProcessing = DtdProcessing.Prohibit,
        XmlResolver = null, MaxCharactersInDocument = MaxXmlCharacters, MaxCharactersFromEntities = 1024,
        IgnoreComments = true, CloseInput = false };
    private static string Get(IReadOnlyDictionary<string, string> values, string key) => values.GetValueOrDefault(key, "");
    private static void RequireId(string value) { if (!IdentifierPattern().IsMatch(value)) Fail("workbook_invalid_identifier"); }
    private static void RequireText(string value, int max)
    {
        if (value.Length > max) Fail("workbook_limits_exceeded");
        try { XmlConvert.VerifyXmlChars(value); } catch (XmlException) { Fail("workbook_invalid_text"); }
    }
    private static void Fail(string code) => throw new DemoValidationException(code);
    private static Row MakeRow(uint number, IEnumerable<string> values, uint style, double height)
    {
        var row = new Row { RowIndex = number, Height = height, CustomHeight = true };
        var column = 'A';
        foreach (var value in values) row.Append(TextCell($"{column++}{number}", value, style));
        return row;
    }
    private static Cell TextCell(string reference, string text, uint style) => new()
    {
        CellReference = reference, StyleIndex = style, DataType = CellValues.InlineString,
        InlineString = new InlineString(new Text(text) { Space = SpaceProcessingModeValues.Preserve })
    };
    private static Stylesheet Styles() => new(
        new Fonts(new Font(new FontSize { Val = 11 }, new Color { Rgb = "FF152C47" }, new FontName { Val = "Calibri" }),
            new Font(new Bold(), new FontSize { Val = 12 }, new Color { Rgb = "FFFFFFFF" }, new FontName { Val = "Calibri" })),
        new Fills(new Fill(new PatternFill { PatternType = PatternValues.None }), new Fill(new PatternFill { PatternType = PatternValues.Gray125 }),
            new Fill(new PatternFill(new ForegroundColor { Rgb = "FF173D60" }, new BackgroundColor { Indexed = 64 }) { PatternType = PatternValues.Solid }),
            new Fill(new PatternFill(new ForegroundColor { Rgb = "FFE7F3FF" }, new BackgroundColor { Indexed = 64 }) { PatternType = PatternValues.Solid })),
        new Borders(new Border(new LeftBorder(), new RightBorder(), new TopBorder(), new BottomBorder(), new DiagonalBorder())),
        new CellStyleFormats(new CellFormat()),
        new CellFormats(new CellFormat(),
            new CellFormat(new Alignment { WrapText = true, Vertical = VerticalAlignmentValues.Center }) { FontId = 1, FillId = 2, ApplyFont = true, ApplyFill = true, ApplyAlignment = true, NumberFormatId = 49, ApplyNumberFormat = true },
            new CellFormat(new Alignment { WrapText = true, Vertical = VerticalAlignmentValues.Top }) { FontId = 0, ApplyAlignment = true, NumberFormatId = 49, ApplyNumberFormat = true },
            new CellFormat(new Alignment { WrapText = true, Vertical = VerticalAlignmentValues.Top }) { FontId = 0, FillId = 3, ApplyFill = true, ApplyAlignment = true, NumberFormatId = 49, ApplyNumberFormat = true }),
        new CellStyles(new CellStyle { Name = "Normal", FormatId = 0, BuiltinId = 0 }));
}

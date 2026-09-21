namespace PqcEnterpriseDemo;

public class DemoStoreException(string code) : Exception(code)
{
    public string Code { get; } = code;
}

public sealed class DemoValidationException(string code) : DemoStoreException(code);
public sealed class DemoConflictException(string code) : DemoStoreException(code);

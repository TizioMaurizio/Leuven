using Xunit;

namespace Project.Tests;

public class ClassNameTests
{
    [Fact]
    public void MethodName_WhenCondition_ThenExpectedResult()
    {
        var sut = new ClassName();

        var result = sut.MethodName("input");

        Assert.Equal("expected", result);
    }
}

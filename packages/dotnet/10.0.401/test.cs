record Point(int X, int Y);

public class Test
{
    public static void Main(string[] args)
    {
        int[] values = [1, 2, 3];
        var p = new Point(values.Length, values.Sum());
        Console.WriteLine(p == new Point(3, 6) ? "OK" : "FAIL");
    }
}

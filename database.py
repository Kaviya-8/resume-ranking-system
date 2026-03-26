import mysql.connector

def get_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Kiruthika0104!",
        database="resume_ranking",
    )
    return connection

'''
def factorial(n):
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result

# Test the function
num = 5
print(factorial(num))  # Expected output: 120

---------------------------------------
#include <stdio.h>

int factorial(int n) {
    int result = 1;
    for(int i = 2; i <= n; i++) {
        result *= i;
    }
    return result;
}

int main() {
    int num = 5;
    printf("%d\n", factorial(num));
    return 0;
}

--------------------------
public class Main {
    public static int factorial(int n) {
        int result = 1;
        for (int i = 2; i <= n; i++) {
            result *= i;
        }
        return result;
    }

    public static void main(String[] args) {
        int num = 5;
        System.out.println(factorial(num));
    }
}
'''






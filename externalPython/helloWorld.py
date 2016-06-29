import time

print("Hello World")

fileName = "C:\Users\Kidscom\Documents\test.txt"
target = open(fileName, 'w')

target.truncate()

target.write("Test\n")
target.write("External Python\n")
target.close()

time.sleep(5)

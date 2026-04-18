from watchfiles import watch
import sys

print("Watching backend/")
for changes in watch("backend/"):
    print(changes)
    sys.exit(0)

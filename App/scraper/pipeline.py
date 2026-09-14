import subprocess
import sys
import os


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


STEPS = [
    ("Crawler", "App/scraper/crawler.py"),
    ("Parser", "App/scraper/parser.py"),
    ("Knowledge Base Builder", "App/scraper/knowledge_base/builder.py"),
    ("Chunker", "App/scraper/knowledge_base/chunker.py"),
    ("Vector Store", "App/scraper/knowledge_base/vector_store.py"),
]


def run_step(name, script):

    print("\n" + "=" * 60)
    print(f"RUNNING: {name}")
    print("=" * 60)

    script_path = os.path.join(BASE_DIR, script)

    result = subprocess.run(
        [sys.executable, script_path],
        cwd=BASE_DIR
    )

    if result.returncode != 0:
        print(f"\nERROR: {name} failed.")
        print("Pipeline stopped.")
        sys.exit(result.returncode)

    print(f"\n{name} completed successfully!")


def main():

    print("\n")
    print("=" * 60)
    print("AUTOMATED RAG KNOWLEDGE BASE PIPELINE")
    print("=" * 60)

    for name, script in STEPS:
        run_step(name, script)

    print("\n")
    print("=" * 60)
    print("PIPELINE COMPLETED SUCCESSFULLY!")
    print("=" * 60)

    print("\nKnowledge Base is now updated.")
    print("You can start the RAG generator next.")


if __name__ == "__main__":
    main()
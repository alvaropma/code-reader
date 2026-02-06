# main.py

from github_reader import GitHubClient


def prompt_repository_info() -> tuple[str, str]:
    """
    Ask the user for a GitHub repository in the form owner/repo,
    and return (owner, repo).
    """
    while True:
        repo_full_name = input(
            "Enter the GitHub repository (format 'owner/repo', e.g. 'torvalds/linux'): "
        ).strip()

        if "/" not in repo_full_name:
            print("Invalid format. Please use 'owner/repo'.")
            continue

        owner, repo = repo_full_name.split("/", 1)
        if not owner or not repo:
            print("Invalid format. Owner or repo missing.")
            continue

        return owner, repo


def main() -> None:
    """
    Entry point for the program.
    """
    print("=== GitHub Code Reader ===")
    print("This tool lists Python files in a GitHub repository and lets you read them.\n")

    try:
        client = GitHubClient()
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Make sure your .env file contains a valid GITHUB_TOKEN.")
        return

    owner, repo = prompt_repository_info()

    try:
        python_files = client.list_python_files(owner, repo)
    except Exception as e:
        print(f"Error while listing files: {e}")
        return

    if not python_files:
        print("No Python files (.py) found in this repository (within the search depth).")
        return

    print("\nFound Python files:")
    for idx, path in enumerate(python_files, start=1):
        print(f"{idx}. {path}")

    while True:
        choice = input(
            "\nEnter the number of the file you want to read (or 'q' to quit): "
        ).strip()

        if choice.lower() == "q":
            print("Goodbye!")
            break

        if not choice.isdigit():
            print("Please enter a valid number or 'q' to quit.")
            continue

        index = int(choice)
        if index < 1 or index > len(python_files):
            print(f"Please choose a number between 1 and {len(python_files)}.")
            continue

        selected_path = python_files[index - 1]

        try:
            content = client.read_file_content(owner, repo, selected_path)
        except Exception as e:
            print(f"Error while reading file: {e}")
            continue

        print("\n" + "=" * 80)
        print(f"File: {selected_path}")
        print("=" * 80)
        print(content)
        print("=" * 80)


if __name__ == "__main__":
    main()

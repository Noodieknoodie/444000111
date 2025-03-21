import os

# List of directories to ensure exist
directories = [
    "backend",
    "backend/data",
    "backend/env",
    "backend/config",
    "backend/database",
    "backend/models",
    "backend/api",
    "backend/utils",
    "backend/tests"
]

# List of files to ensure exist, with their paths relative to the root
files = [
    "backend/__init__.py",
    "backend/main.py",
    "backend/requirements.txt",
    "backend/config/__init__.py",
    "backend/config/settings.py",
    "backend/database/__init__.py",
    "backend/database/connection.py",
    "backend/models/__init__.py",
    "backend/models/client.py",
    "backend/models/payment.py",
    "backend/models/contract.py",
    "backend/models/file.py",
    "backend/api/__init__.py",
    "backend/api/clients.py",
    "backend/api/payments.py",
    "backend/api/contracts.py",
    "backend/api/files.py",
    "backend/utils/__init__.py",
    "backend/utils/file_manager.py",
    "backend/utils/period_manager.py",
    "backend/tests/__init__.py",
    "backend/tests/conftest.py",
    "backend/tests/test_database.py",
    "backend/tests/test_api.py"
]

def create_directories():
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")
        else:
            print(f"Directory exists: {directory}")

def create_files():
    for file_path in files:
        # Create the file only if it does not already exist
        if not os.path.exists(file_path):
            # Ensure the parent directory exists (should be already created by create_directories())
            parent_dir = os.path.dirname(file_path)
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir)
            with open(file_path, "w") as file:
                # Write a comment with the relative file path starting from 'backend'
                file.write(f"# {file_path}\n")
            print(f"Created file: {file_path}")
        else:
            print(f"File exists: {file_path}")

def main():
    create_directories()
    create_files()
    print("Project structure is set up.")

if __name__ == "__main__":
    main()

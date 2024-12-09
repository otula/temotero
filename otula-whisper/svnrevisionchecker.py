import subprocess

def get_svn_revision():
    try:
        # Run the 'svn info' command and capture the output
        result = subprocess.run(['svn', 'info'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Check if the command was successful
        if result.returncode == 0:
            # Parse the output to find the version number (revision number)
            for line in result.stdout.splitlines():
                if line.startswith('Revision:'):
                    version = line.split()[1]
                    return version
        else:
            print(f"Error running svn info: {result.stderr}")
            return None
    except FileNotFoundError:
        print("Error: 'svn' command not found. Please ensure that Subversion is installed and accessible in your PATH.")
        return None
    except subprocess.SubprocessError as e:
        print(f"Subprocess error occurred: {e}")
        return None


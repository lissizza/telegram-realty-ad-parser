# Development Setup

## VS Code / Cursor with Docker

### Method 1: Dev Containers (Recommended)

1. **Install Dev Containers extension** in VS Code/Cursor
2. **Open project** in VS Code/Cursor
3. **Press `Ctrl+Shift+P`** → "Dev Containers: Reopen in Container"
4. **Wait** for container to build and start
5. **VS Code will automatically** use the Python interpreter from Docker

### Method 2: Remote Development

1. **Install Remote Development extension** in VS Code/Cursor
2. **Open project** in VS Code/Cursor
3. **Press `Ctrl+Shift+P`** → "Remote-Containers: Attach to Running Container"
4. **Select** `rent-no-fees-app-1` container
5. **VS Code will connect** to the running container

### Method 3: Local Development

If you want to work locally without Docker:

1. **Create virtual environment**:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Set Python interpreter** in VS Code/Cursor:
   - Press `Ctrl+Shift+P`
   - Type "Python: Select Interpreter"
   - Choose `./venv/bin/python` (or `./venv/Scripts/python.exe` on Windows)

## Available Tasks

Press `Ctrl+Shift+P` → "Tasks: Run Task" to see available tasks:

- **Docker: Start Services** - Start all Docker services
- **Docker: Stop Services** - Stop all Docker services
- **Docker: Restart App** - Restart only the app container
- **Python: Run Flake8** - Run linting
- **Python: Format with Black** - Format code
- **Python: Run Tests** - Run all tests
- **Python: Install Dependencies** - Install Python packages

## Debugging

1. **Set breakpoints** in your code
2. **Press F5** to start debugging
3. **Choose configuration**:
   - "Python: FastAPI App" - Debug FastAPI server
   - "Python: Telegram Bot" - Debug Telegram bot
   - "Python: Run Tests" - Debug tests

## Troubleshooting

### Python Interpreter Issues

If VS Code shows "Invalid Interpreter":

1. **Check Docker is running**:

   ```bash
   docker-compose ps
   ```

2. **Restart VS Code** and try again

3. **Manual interpreter selection**:
   - Press `Ctrl+Shift+P`
   - Type "Python: Select Interpreter"
   - Choose `/usr/local/bin/python` (Docker) or `./venv/bin/python` (local)

### Container Issues

If Dev Container fails to start:

1. **Rebuild container**:

   ```bash
   docker-compose down
   docker-compose up --build
   ```

2. **Check logs**:
   ```bash
   docker-compose logs app
   ```

## Recommended Extensions

Install these extensions for the best experience:

- **Python** - Core Python support
- **Dev Containers** - Docker container support
- **Remote Development** - Remote development support
- **Black Formatter** - Code formatting
- **Flake8** - Linting
- **Pytest** - Testing support
- **Docker** - Docker support

const { app, BrowserWindow, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let apiProcess;

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

function startApiServer() {
    const apiPath = isDev
        ? path.join(__dirname, '..', '..', 'api')
        : path.join(process.resourcesPath, 'api');

    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

    apiProcess = spawn(pythonCmd, [
        '-m', 'uvicorn',
        'app.main:app',
        '--host', '127.0.0.1',
        '--port', '8765'
    ], {
        cwd: apiPath,
        stdio: 'inherit',
        shell: true
    });

    apiProcess.on('error', (err) => {
        console.error('Failed to start API server:', err);
    });
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1000,
        minHeight: 700,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
        },
        icon: path.join(__dirname, '..', 'public', 'icon.ico'),
        title: 'TG Workspace',
        autoHideMenuBar: true,
    });

    // Open external links in browser
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        if (url.startsWith('https://t.me/') || url.startsWith('tg://')) {
            shell.openExternal(url);
            return { action: 'deny' };
        }
        return { action: 'allow' };
    });

    if (isDev) {
        mainWindow.loadURL('http://localhost:5173');
        mainWindow.webContents.openDevTools();
    } else {
        mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
    }
}

app.whenReady().then(() => {
    startApiServer();

    // Wait for API to start
    setTimeout(createWindow, 2000);

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    if (apiProcess) {
        apiProcess.kill();
    }
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('before-quit', () => {
    if (apiProcess) {
        apiProcess.kill();
    }
});

using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading.Tasks;
using System.Windows;
using Microsoft.Win32;

namespace FactorioVideoToBlueprint
{
    public partial class MainWindow : Window
    {
        private string? _bridgePath;
        private string _pythonExecutable = "python";
        private Process? _activeCompileProc = null;

        public MainWindow()
        {
            InitializeComponent();
            FindEnvironmentPaths();
            Loaded += MainWindow_Loaded;
        }

        private void FindEnvironmentPaths()
        {
            // Python bridge path discovery
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string[] possiblePaths = new[]
            {
                Path.Combine(baseDir, "bridge.py"),
                Path.Combine(baseDir, "..", "..", "..", "..", "bridge.py"),
                Path.Combine(baseDir, "..", "bridge.py"),
                Path.Combine(Directory.GetCurrentDirectory(), "bridge.py")
            };

            foreach (var p in possiblePaths)
            {
                string full = Path.GetFullPath(p);
                if (File.Exists(full))
                {
                    _bridgePath = full;
                    break;
                }
            }

            // Check if python is accessible
            _pythonExecutable = "python";
        }

        private async void MainWindow_Loaded(object sender, RoutedEventArgs e)
        {
            try
            {
                // Initialize WebView2
                string userDataFolder = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "FactorioVideoToBlueprint", "WebView2Data"
                );
                Directory.CreateDirectory(userDataFolder);

                var env = await Microsoft.Web.WebView2.Core.CoreWebView2Environment.CreateAsync(
                    userDataFolder: userDataFolder
                );

                await webView.EnsureCoreWebView2Async(env);

                // Disable default context menu & dev accelerators in production if desired, but keep useful features
                webView.CoreWebView2.Settings.IsStatusBarEnabled = false;
                webView.CoreWebView2.Settings.AreDevToolsEnabled = true;
                webView.CoreWebView2.Settings.IsZoomControlEnabled = true;

                // Sync whole-app zoom factor with UI
                webView.ZoomFactorChanged += (s, ev) =>
                {
                    Dispatcher.Invoke(() =>
                    {
                        double factor = webView.ZoomFactor;
                        SendToWeb(new { type = "ui_zoom_changed", factor, percent = (int)Math.Round(factor * 100) });
                    });
                };

                // Virtual host or direct local file navigation
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                string wwwrootDir = Path.Combine(baseDir, "wwwroot");
                if (!Directory.Exists(wwwrootDir))
                {
                    // Fallback to project root wwwroot during development
                    string devWwwroot = Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", "wwwroot"));
                    if (Directory.Exists(devWwwroot))
                    {
                        wwwrootDir = devWwwroot;
                    }
                }

                if (Directory.Exists(wwwrootDir))
                {
                    webView.CoreWebView2.SetVirtualHostNameToFolderMapping(
                        "app.local",
                        wwwrootDir,
                        Microsoft.Web.WebView2.Core.CoreWebView2HostResourceAccessKind.Allow
                    );
                    webView.CoreWebView2.Navigate("https://app.local/index.html");
                }
                else
                {
                    string htmlPath = Path.Combine(baseDir, "wwwroot", "index.html");
                    webView.CoreWebView2.Navigate(htmlPath);
                }

                webView.CoreWebView2.WebMessageReceived += OnWebMessageReceived;
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    $"WebView2 başlatılırken hata oluştu: {ex.Message}\n\nLütfen Microsoft Edge WebView2 Runtime yüklü olduğundan emin olun.",
                    "Hata", MessageBoxButton.OK, MessageBoxImage.Error
                );
            }
        }

        private async void OnWebMessageReceived(object? sender, Microsoft.Web.WebView2.Core.CoreWebView2WebMessageReceivedEventArgs e)
        {
            try
            {
                string rawJson = e.WebMessageAsJson;
                var node = JsonNode.Parse(rawJson);
                if (node == null) return;

                string action = node["action"]?.ToString() ?? "";

                switch (action)
                {
                    case "select_file":
                        await HandleSelectFileAsync();
                        break;

                    case "load_demo":
                        await HandleLoadDemoAsync();
                        break;

                    case "get_preview":
                        string path = node["path"]?.ToString() ?? "__demo__";
                        int h = node["target_h"]?.GetValue<int>() ?? 16;
                        int fIdx = node["frame_idx"]?.GetValue<int>() ?? 0;
                        await HandleGetPreviewAsync(path, h, fIdx);
                        break;

                    case "estimate_stats":
                        string statsParams = node["params"]?.ToJsonString() ?? "{}";
                        await HandleEstimateStatsAsync(statsParams);
                        break;

                    case "compile":
                        string compileParams = node["params"]?.ToJsonString() ?? "{}";
                        await HandleCompileAsync(compileParams);
                        break;

                    case "abort":
                        HandleAbort();
                        break;

                    case "copy_clipboard":
                        string textToCopy = node["text"]?.ToString() ?? "";
                        HandleCopyClipboard(textToCopy);
                        break;

                    case "save_file":
                        string content = node["content"]?.ToString() ?? "";
                        string defName = node["defaultName"]?.ToString() ?? "blueprint.txt";
                        HandleSaveFile(content, defName);
                        break;

                    case "set_ui_zoom":
                        double delta = node["delta"]?.GetValue<double>() ?? 0.0;
                        if (Math.Abs(delta) > 0.001)
                        {
                            double newFactor = Math.Clamp(webView.ZoomFactor + delta, 0.5, 3.0);
                            webView.ZoomFactor = Math.Round(newFactor, 2);
                        }
                        break;

                    case "reset_ui_zoom":
                        webView.ZoomFactor = 1.0;
                        break;
                }
            }
            catch (Exception ex)
            {
                SendToWeb(new { type = "error", message = ex.Message });
            }
        }

        private void Window_DragOver(object sender, DragEventArgs e)
        {
            if (e.Data.GetDataPresent(DataFormats.FileDrop))
            {
                e.Effects = DragDropEffects.Copy;
            }
            else
            {
                e.Effects = DragDropEffects.None;
            }
            e.Handled = true;
        }

        private async void Window_Drop(object sender, DragEventArgs e)
        {
            if (e.Data.GetDataPresent(DataFormats.FileDrop))
            {
                var files = e.Data.GetData(DataFormats.FileDrop) as string[];
                if (files != null && files.Length > 0)
                {
                    string droppedPath = files[0];
                    string result = await RunPythonBridgeAsync($"info \"{droppedPath}\"");
                    SendRawToWeb(result);
                }
            }
        }

        private async Task HandleSelectFileAsync()
        {
            var dialog = new OpenFileDialog
            {
                Title = "Select Video or GIF File",
                Filter = "Supported Media (*.mp4;*.gif;*.avi;*.mkv;*.webm;*.mov)|*.mp4;*.gif;*.avi;*.mkv;*.webm;*.mov|All Files (*.*)|*.*",
                CheckFileExists = true
            };

            if (dialog.ShowDialog() == true)
            {
                string selectedPath = dialog.FileName;
                string result = await RunPythonBridgeAsync($"info \"{selectedPath}\"");
                SendRawToWeb(result);
            }
        }

        private async Task HandleLoadDemoAsync()
        {
            string result = await RunPythonBridgeAsync("demo_info");
            SendRawToWeb(result);
        }

        private async Task HandleGetPreviewAsync(string path, int targetH, int frameIdx)
        {
            string result = await RunPythonBridgeAsync($"preview_frame \"{path}\" {targetH} {frameIdx}");
            SendRawToWeb(result);
        }

        private async Task HandleEstimateStatsAsync(string jsonParams)
        {
            string result = await RunPythonBridgeAsync("estimate_stats", jsonParams);
            SendRawToWeb(result);
        }

        private async Task HandleCompileAsync(string jsonParams)
        {
            if (string.IsNullOrEmpty(_bridgePath) || !File.Exists(_bridgePath))
            {
                SendToWeb(new { type = "result", success = false, error = "bridge.py dosyası bulunamadı." });
                return;
            }

            await Task.Run(() =>
            {
                try
                {
                    string workDir = Path.GetDirectoryName(_bridgePath) ?? Directory.GetCurrentDirectory();
                    var psi = new ProcessStartInfo
                    {
                        FileName = _pythonExecutable,
                        Arguments = $"\"{_bridgePath}\" compile",
                        WorkingDirectory = workDir,
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        RedirectStandardInput = true,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        StandardInputEncoding = new UTF8Encoding(false),
                        StandardOutputEncoding = Encoding.UTF8,
                        StandardErrorEncoding = Encoding.UTF8
                    };
                    psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
                    psi.EnvironmentVariables["PYTHONUTF8"] = "1";

                    using var proc = new Process { StartInfo = psi };
                    _activeCompileProc = proc;
                    var errBuilder = new StringBuilder();

                    proc.OutputDataReceived += (s, e) =>
                    {
                        if (!string.IsNullOrEmpty(e.Data))
                        {
                            Dispatcher.Invoke(() => SendRawToWeb(e.Data));
                        }
                    };

                    proc.ErrorDataReceived += (s, e) =>
                    {
                        if (!string.IsNullOrEmpty(e.Data))
                        {
                            errBuilder.AppendLine(e.Data);
                        }
                    };

                    proc.Start();
                    proc.BeginOutputReadLine();
                    proc.BeginErrorReadLine();

                    // Send arguments via stdin safely
                    if (!string.IsNullOrEmpty(jsonParams))
                    {
                        proc.StandardInput.Write(jsonParams);
                        proc.StandardInput.Flush();
                        proc.StandardInput.Close();
                    }
                    else
                    {
                        proc.StandardInput.Close();
                    }

                    proc.WaitForExit();
                    if (_activeCompileProc != null && proc.ExitCode != 0)
                    {
                        string err = errBuilder.ToString();
                        Dispatcher.Invoke(() => SendToWeb(new { type = "result", success = false, error = err }));
                    }
                }
                catch (Exception ex)
                {
                    if (_activeCompileProc != null)
                    {
                        Dispatcher.Invoke(() => SendToWeb(new { type = "result", success = false, error = ex.Message }));
                    }
                }
                finally
                {
                    _activeCompileProc = null;
                }
            });
        }

        private void HandleAbort()
        {
            try
            {
                var proc = _activeCompileProc;
                _activeCompileProc = null;
                if (proc != null && !proc.HasExited)
                {
                    proc.Kill(entireProcessTree: true);
                }
                SendToWeb(new { type = "aborted", success = false, message = "Derleme kullanıcı tarafından iptal edildi." });
            }
            catch (Exception ex)
            {
                SendToWeb(new { type = "aborted", success = false, message = ex.Message });
            }
        }

        private void HandleCopyClipboard(string text)
        {
            try
            {
                Clipboard.SetText(text);
                SendToWeb(new { type = "clipboard_copied", success = true });
            }
            catch (Exception ex)
            {
                SendToWeb(new { type = "clipboard_copied", success = false, error = ex.Message });
            }
        }

        private void HandleSaveFile(string content, string defaultName)
        {
            var dialog = new SaveFileDialog
            {
                Title = "Save Blueprint File",
                FileName = defaultName,
                Filter = "Text Files (*.txt)|*.txt|All Files (*.*)|*.*",
                DefaultExt = ".txt"
            };

            if (dialog.ShowDialog() == true)
            {
                try
                {
                    File.WriteAllText(dialog.FileName, content, Encoding.UTF8);
                    SendToWeb(new { type = "file_saved", success = true, path = dialog.FileName });
                }
                catch (Exception ex)
                {
                    SendToWeb(new { type = "file_saved", success = false, error = ex.Message });
                }
            }
        }

        private async Task<string> RunPythonBridgeAsync(string commandAndArgs, string? stdinInput = null)
        {
            if (string.IsNullOrEmpty(_bridgePath) || !File.Exists(_bridgePath))
            {
                return JsonSerializer.Serialize(new { success = false, error = "bridge.py bulunamadı." });
            }

            return await Task.Run(() =>
            {
                try
                {
                    string workDir = Path.GetDirectoryName(_bridgePath) ?? Directory.GetCurrentDirectory();
                    var psi = new ProcessStartInfo
                    {
                        FileName = _pythonExecutable,
                        Arguments = $"\"{_bridgePath}\" {commandAndArgs}",
                        WorkingDirectory = workDir,
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        RedirectStandardInput = true,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        StandardInputEncoding = new UTF8Encoding(false),
                        StandardOutputEncoding = Encoding.UTF8,
                        StandardErrorEncoding = Encoding.UTF8
                    };
                    psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
                    psi.EnvironmentVariables["PYTHONUTF8"] = "1";

                    using var proc = Process.Start(psi);
                    if (proc == null) return JsonSerializer.Serialize(new { success = false, error = "Python başlatılamadı." });

                    if (stdinInput != null)
                    {
                        proc.StandardInput.Write(stdinInput);
                        proc.StandardInput.Flush();
                        proc.StandardInput.Close();
                    }
                    else
                    {
                        proc.StandardInput.Close();
                    }

                    string output = proc.StandardOutput.ReadToEnd();
                    string error = proc.StandardError.ReadToEnd();
                    proc.WaitForExit();

                    if (!string.IsNullOrWhiteSpace(output))
                    {
                        return output.Trim();
                    }
                    if (!string.IsNullOrWhiteSpace(error))
                    {
                        return JsonSerializer.Serialize(new { success = false, error });
                    }
                    return JsonSerializer.Serialize(new { success = true });
                }
                catch (Exception ex)
                {
                    return JsonSerializer.Serialize(new { success = false, error = ex.Message });
                }
            });
        }

        private void SendToWeb(object obj)
        {
            string json = JsonSerializer.Serialize(obj);
            SendRawToWeb(json);
        }

        private void SendRawToWeb(string rawJson)
        {
            if (webView?.CoreWebView2 != null)
            {
                webView.CoreWebView2.PostWebMessageAsJson(rawJson);
            }
        }
    }
}
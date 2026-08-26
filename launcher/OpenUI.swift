import Cocoa
import Darwin
import Security

@_silgen_name("SecTranslocateCreateOriginalPathForURL")
func SecTranslocateCreateOriginalPathForURL(
    _ translocatedURL: CFURL,
    _ error: UnsafeMutablePointer<Unmanaged<CFError>?>?
) -> Unmanaged<CFURL>?

class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    var server: Process?
    var pollTimer: Timer?

    let port = 3000
    var url: URL { URL(string: "http://127.0.0.1:\(port)")! }
    lazy var repo: URL = Self.findProjectRoot()

    func applicationDidFinishLaunching(_ notification: Notification) {
        buildWindow()
        startServer()
        pollUntilUpAndOpenBrowser()
    }

    func applicationWillTerminate(_ notification: Notification) {
        pollTimer?.invalidate()
        if let server, server.isRunning {
            server.terminate()
            server.waitUntilExit()
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    private func buildWindow() {
        let rect = NSRect(x: 0, y: 0, width: 420, height: 160)
        window = NSWindow(
            contentRect: rect,
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "YouTube Channel Corpus"
        window.center()

        let label = NSTextField(wrappingLabelWithString: """
        Starting the app…

        Your browser should open to http://localhost:3000
        Close this window to stop.
        """)
        label.frame = NSRect(x: 20, y: 20, width: 380, height: 120)
        label.isSelectable = false
        window.contentView?.addSubview(label)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func log(_ message: String) {
        let line = "\(ISO8601DateFormatter().string(from: Date())) \(message)\n"
        let logURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Logs/youtube-channel-corpus-open-ui.log")
        if let handle = try? FileHandle(forWritingTo: logURL) {
            handle.seekToEndOfFile()
            handle.write(Data(line.utf8))
            try? handle.close()
        } else {
            try? line.write(to: logURL, atomically: true, encoding: .utf8)
        }
        NSLog("%@", message)
    }

    private static func originalBundleURL() -> URL {
        let launched = Bundle.main.bundleURL
        var error: Unmanaged<CFError>?
        if let original = SecTranslocateCreateOriginalPathForURL(launched as CFURL, &error) {
            return original.takeRetainedValue() as URL
        }
        return launched
    }

    private static func findProjectRoot() -> URL {
        let fm = FileManager.default
        var dirs: [URL] = [
            originalBundleURL().deletingLastPathComponent(),
            Bundle.main.bundleURL.deletingLastPathComponent(),
            fm.homeDirectoryForCurrentUser.appendingPathComponent("YouTube-Transcript-Scraper"),
        ]
        dirs.append(URL(fileURLWithPath: fm.currentDirectoryPath))
        for dir in dirs {
            let script = dir.appendingPathComponent("start.sh")
            let app = dir.appendingPathComponent("app.py")
            if fm.fileExists(atPath: script.path), fm.fileExists(atPath: app.path) {
                return dir
            }
        }
        return originalBundleURL().deletingLastPathComponent()
    }

    private func startServer() {
        let script = repo.appendingPathComponent("start.sh")
        log("Looking for project in \(repo.path)")
        guard FileManager.default.fileExists(atPath: script.path) else {
            log("start.sh not found at \(script.path) (launched from \(Bundle.main.bundlePath))")
            showAlert("Could not find start.sh. Put Open UI.app in the YouTube-Transcript-Scraper folder (next to start.sh) and open it from there.")
            NSApp.terminate(nil)
            return
        }

        var env = ProcessInfo.processInfo.environment
        let extraPath = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
        env["PATH"] = extraPath + ":" + (env["PATH"] ?? "")
        env["PORT"] = String(port)
        env["YT_SCRAPER_SKIP_BROWSER"] = "1"

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = [script.path]
        process.currentDirectoryURL = repo
        process.environment = env

        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        process.standardInput = FileHandle.nullDevice

        do {
            try process.run()
            server = process
            log("Started start.sh pid=\(process.processIdentifier)")
        } catch {
            log("Failed to start: \(error)")
            showAlert("Could not start the app: \(error.localizedDescription)")
        }
    }

    private func pollUntilUpAndOpenBrowser() {
        var tries = 0
        pollTimer = Timer.scheduledTimer(withTimeInterval: 0.4, repeats: true) { [weak self] timer in
            guard let self else { return }
            tries += 1
            if self.portOpen() {
                timer.invalidate()
                self.log("Port \(self.port) is up; opening browser")
                NSWorkspace.shared.open(self.url)
                if let label = self.window.contentView?.subviews.first as? NSTextField {
                    label.stringValue = """
                    Running.

                    Browser: http://localhost:3000
                    Close this window to stop.
                    """
                }
            } else if tries >= 90 {
                timer.invalidate()
                self.log("Timed out waiting for port \(self.port)")
                self.showAlert("The app did not start on port \(self.port). See ~/Library/Logs/youtube-channel-corpus-open-ui.log")
            }
        }
    }

    private func portOpen() -> Bool {
        let sock = socket(AF_INET, SOCK_STREAM, 0)
        defer { close(sock) }
        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = in_port_t(port).bigEndian
        inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr)
        let result = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.connect(sock, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        return result == 0
    }

    private func showAlert(_ message: String) {
        let alert = NSAlert()
        alert.messageText = "YouTube Channel Corpus"
        alert.informativeText = message
        alert.alertStyle = .warning
        alert.runModal()
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()

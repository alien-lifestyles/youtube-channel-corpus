import Foundation

let repo = Bundle.main.bundleURL.deletingLastPathComponent().path
let script = (repo as NSString).appendingPathComponent("start.sh")

func shellQuote(_ s: String) -> String {
    "'" + s.replacingOccurrences(of: "'", with: "'\\''") + "'"
}

let command = "cd \(shellQuote(repo)) && exec ./start.sh"
let process = Process()
process.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
process.arguments = [
    "-e",
    "tell application \"Terminal\"\nactivate\ndo script \(shellQuote(command))\nend tell",
]
try process.run()
process.waitUntilExit()
exit(process.terminationStatus)

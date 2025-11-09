import Foundation
import AVFoundation
import ShazamKit

// Simple ShazamKit-based matcher CLI
// Usage: shazamcli /path/to/file

let args = CommandLine.arguments
guard args.count >= 2 else {
    fputs("Usage: shazamcli <audio-file>\n", stderr)
    exit(2)
}

let filePath = args[1]
let fileURL = URL(fileURLWithPath: filePath)

// parse optional flags
var chunkSeconds: Double = 20.0
var overlapSeconds: Double = 5.0
var i = 2
while i < args.count {
    let a = args[i]
    if a == "--chunk", i + 1 < args.count {
        chunkSeconds = Double(args[i+1]) ?? chunkSeconds
        i += 2
    } else if a == "--overlap", i + 1 < args.count {
        overlapSeconds = Double(args[i+1]) ?? overlapSeconds
        i += 2
    } else {
        i += 1
    }
}

class Matcher: NSObject, SHSessionDelegate {
    let session = SHSession()
    var results: [(title: String, artist: String)] = []
    private var semaphore = DispatchSemaphore(value: 0)

    override init() {
        super.init()
        session.delegate = self
    }

    func matchFile(_ url: URL) throws {
        let file = try AVAudioFile(forReading: url)
        let format = file.processingFormat

        // Read the entire file into a buffer (may be large for very long captures)
        let totalFrames = AVAudioFrameCount(file.length)
        guard let fullBuffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: totalFrames) else {
            throw NSError(domain: "ShazamCLI", code: 1, userInfo: [NSLocalizedDescriptionKey: "Failed to create buffer"]) }
        try file.read(into: fullBuffer)

        // compute window and step in frames
        let sampleRate = format.sampleRate
        let channels = Int(format.channelCount)
        let windowFrames = AVAudioFrameCount(max(1, Int(chunkSeconds * sampleRate)))
        let overlapFrames = AVAudioFrameCount(max(0, Int(overlapSeconds * sampleRate)))
        let stepFrames = windowFrames > overlapFrames ? windowFrames - overlapFrames : windowFrames

        var position: AVAudioFramePosition = 0
        var seenAny = false

        while position < AVAudioFramePosition(fullBuffer.frameLength) {
            let framesLeft = AVAudioFrameCount(fullBuffer.frameLength) - AVAudioFrameCount(position)
            let thisWindow = min(windowFrames, framesLeft)

            // create a buffer for this window
            guard let windowBuf = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: thisWindow) else {
                break
            }
            windowBuf.frameLength = thisWindow

            // copy channel data (assumes float data)
            if let src = fullBuffer.floatChannelData, let dst = windowBuf.floatChannelData {
                let start = Int(position)
                for ch in 0..<channels {
                    let s = src[ch]
                    let d = dst[ch]
                    // copy samples
                    memcpy(d, s.advanced(by: start), Int(thisWindow) * MemoryLayout<Float>.size)
                }
            } else {
                // fallback: append entire buffer
                try? SHSignatureGenerator().append(fullBuffer, at: nil)
            }

            let signatureGenerator = SHSignatureGenerator()
            try? signatureGenerator.append(windowBuf, at: nil)
            if let signature = try? signatureGenerator.signature() {
                session.match(signature)
                // wait briefly for delegate to signal
                _ = semaphore.wait(timeout: .now() + 6.0)
                seenAny = true
            }

            // advance
            position += AVAudioFramePosition(stepFrames)
        }

        if !seenAny {
            // final attempt: single-signature fallback
            let signatureGenerator = SHSignatureGenerator()
            try? signatureGenerator.append(fullBuffer, at: nil)
            if let signature = try? signatureGenerator.signature() {
                session.match(signature)
                _ = semaphore.wait(timeout: .now() + 6.0)
            }
        }
    }

    func session(_ session: SHSession, didFind match: SHMatch) {
        for item in match.mediaItems {
            let title = item.title ?? "Unknown"
            // Use subtitle as a best-effort artist/album label if available
            let artist = item.subtitle ?? ""
            results.append((title: title, artist: artist))
        }
        // Signal that we got something (if multiple matches appear, delegate will be called multiple times)
        semaphore.signal()
    }
}

do {
    let matcher = Matcher()
    try matcher.matchFile(fileURL)

    // Deduplicate results while preserving order
    var seen = Set<String>()
    for pair in matcher.results {
        let key = pair.title + " - " + pair.artist
        if !seen.contains(key) {
            seen.insert(key)
            if pair.artist.isEmpty {
                print(pair.title)
            } else {
                print("\(pair.title) - \(pair.artist)")
            }
        }
    }
    // If no results, print nothing (Python wrapper will handle fallback)
} catch {
    fputs("Error: \(error)\n", stderr)
    exit(1)
}

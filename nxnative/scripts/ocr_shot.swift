// Read the text off a screenshot with macOS Vision, for driving a game's menus without eyes: a boot that reaches its title screen
// can be navigated on the evidence of what the screen says (and which item is brightest), one press at a time, instead of guessing.
//   swift nxnative/scripts/ocr_shot.swift <screen.png>
// One line per recognized run: x y w h (normalized, origin bottom left, Vision's order) and the text. A dark UI reads better
// brightened first (Pillow: im.point(lambda v: min(255, v * 5))), which is how Skyrim's nearly black menu was read.
// First used in the Skyrim Switch bring-up (docs/BRINGUP_SKYRIM.md), where no vision model was available for the screenshots.
import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count > 1 else { FileHandle.standardError.write("usage: ocr_shot.swift <image>\n".data(using: .utf8)!); exit(2) }
let path = CommandLine.arguments[1]
guard let img = NSImage(contentsOfFile: path), let tiff = img.tiffRepresentation,
      let rep = NSBitmapImageRep(data: tiff), let cg = rep.cgImage else {
    FileHandle.standardError.write("cannot read \(path)\n".data(using: .utf8)!); exit(2)
}
let req = VNRecognizeTextRequest { r, _ in
    guard let obs = r.results as? [VNRecognizedTextObservation] else { return }
    for o in obs {
        guard let t = o.topCandidates(1).first else { continue }
        let b = o.boundingBox
        print(String(format: "%.3f %.3f %.3f %.3f  %@", b.origin.x, b.origin.y, b.width, b.height, t.string))
    }
}
req.recognitionLevel = .accurate
req.usesLanguageCorrection = false
req.recognitionLanguages = ["en-US"]
try VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])

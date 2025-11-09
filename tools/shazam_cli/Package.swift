// swift-tools-version:5.6
import PackageDescription

let package = Package(
    name: "ShazamCLI",
    platforms: [
        .macOS(.v12)
    ],
    products: [
        .executable(name: "shazamcli", targets: ["ShazamCLI"]),
    ],
    targets: [
        .executableTarget(
            name: "ShazamCLI",
            path: "Sources/ShazamCLI"
        )
    ]
)

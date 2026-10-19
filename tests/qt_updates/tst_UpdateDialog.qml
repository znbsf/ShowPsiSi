import QtQuick
import QtQuick.Controls
import QtTest
import "../../ui/qt" as Application

// Actual production component with an inert presentation fixture. No network,
// download, process launch or production test hook is involved.
Item {
    width: 900
    height: 720
    ApplicationWindow {
        id: window
        visible: true
        width: 900
        height: 720
        property bool light: false
        color: light ? "#f5f6f8" : "#181a1f"
        palette.window: light ? "#ffffff" : "#20232a"
        palette.windowText: light ? "#202733" : "#dce1e9"
        palette.base: light ? "#f5f6f8" : "#181a1f"
        palette.text: light ? "#202733" : "#dce1e9"
        palette.button: light ? "#eef0f3" : "#2a2e37"
        palette.buttonText: light ? "#202733" : "#dce1e9"
        QtObject {
            id: appUpdater
            property string currentVersion: "0.1.0"
            property string repositoryUrl: "https://github.com/znbsf/ShowPsiSi"
            property string state: "idle"
            property string edition: "source"
            property string editionLabel: "Qt source build"
            property string status: "Presentation fixture · no network or installer actions"
            property string latestVersion: ""
            property string releaseNotes: ""
            property string assetName: ""
            property string checksum: ""
            property int downloadSize: 0
            property real progress: 0
            property bool busy: false
            property bool installerSupported: false
            property bool canDownload: false
            property bool canInstall: false
            property bool canOpenPortable: false
            property int checks: 0
            property int downloads: 0
            property int installs: 0
            property int portableOpens: 0
            function checkForUpdates() {
                checks++;
            }
            function downloadUpdate() {
                downloads++;
            }
            function installUpdate(confirmed) {
                installs++;
            }
            function cancel() {
            }
            function openRepository() {
            }
            function openReleases() {
            }
            function openPortableDownload() {
                portableOpens++;
            }
        }
        Application.UpdateDialog {
            id: dialog
            lightTheme: window.light
        }
        TestCase {
            name: "UpdateDialogVisualStates"
            when: windowShown
            function init() {
                appUpdater.busy = false;
                appUpdater.edition = "source";
                appUpdater.editionLabel = "Qt source build";
                appUpdater.canOpenPortable = false;
                appUpdater.portableOpens = 0;
                appUpdater.latestVersion = "";
                appUpdater.assetName = "";
                appUpdater.checksum = "";
                appUpdater.canDownload = false;
                appUpdater.canInstall = false;
                appUpdater.checks = 0;
                appUpdater.downloads = 0;
                appUpdater.installs = 0;
                dialog.workBusy = false;
            }
            function cleanup() {
                dialog.close();
            }
            function test_portableBrowserFlow_data() {
                return [
                    {
                        tag: "dark",
                        light: false
                    },
                    {
                        tag: "light",
                        light: true
                    }
                ];
            }
            function test_portableBrowserFlow(data) {
                window.light = data.light;
                appUpdater.edition = "portable";
                appUpdater.editionLabel = "Windows x64 Qt · portable edition (no installation)";
                appUpdater.canOpenPortable = true;
                appUpdater.latestVersion = "0.2.0";
                appUpdater.assetName = "ShowPsiSi-0.2.0-windows-x64-portable.zip";
                appUpdater.checksum = "b".repeat(64);
                appUpdater.downloadSize = 80 * 1048576;
                dialog.open();
                tryCompare(dialog, "opened", true);
                compare(findChild(dialog, "downloadUpdateButton").visible, false);
                compare(findChild(dialog, "installUpdateButton").visible, false);
                const portable = findChild(dialog, "portableUpdateButton");
                verify(portable.visible && portable.enabled);
                verify(findChild(dialog, "updateEditionLabel").text.indexOf("portable") >= 0);
                waitForRendering(dialog.contentItem);
                grabImage(window.contentItem).save("update-dialog-portable-" + data.tag + ".png");
                mouseClick(portable);
                const confirmation = findChild(dialog, "portableUpdateConfirmation");
                tryCompare(confirmation, "opened", true);
                const checksum = findChild(dialog, "portableExpectedChecksum");
                compare(checksum.text, appUpdater.checksum);
                verify(checksum.readOnly && checksum.selectByMouse);
                waitForRendering(confirmation.contentItem);
                grabImage(window.contentItem).save("update-dialog-portable-confirm-" + data.tag + ".png");
                confirmation.close();
                compare(appUpdater.portableOpens, 0);
                mouseClick(portable);
                tryCompare(confirmation, "opened", true);
                mouseClick(findChild(dialog, "confirmPortableUpdateButton"));
                compare(appUpdater.portableOpens, 1);
                compare(appUpdater.installs, 0);
                compare(appUpdater.downloads, 0);
                appUpdater.canOpenPortable = false;
                compare(portable.enabled, false);
                compare(portable.opacity, 0.4);
            }
            function test_disabledContrast_data() {
                return [
                    {
                        tag: "dark",
                        light: false
                    },
                    {
                        tag: "light",
                        light: true
                    }
                ];
            }
            function test_disabledContrast(data) {
                window.light = data.light;
                dialog.open();
                tryCompare(dialog, "opened", true);
                const check = findChild(dialog, "checkUpdatesButton");
                const close = findChild(dialog, "cancelUpdateButton");
                const download = findChild(dialog, "downloadUpdateButton");
                const install = findChild(dialog, "installUpdateButton");
                verify(check && close && download && install);
                compare(check.enabled, true);
                compare(close.enabled, true);
                compare(check.opacity, 1);
                compare(close.opacity, 1);
                compare(check.palette.buttonText, window.palette.buttonText);
                compare(close.palette.buttonText, window.palette.buttonText);
                compare(download.enabled, false);
                compare(install.enabled, false);
                compare(download.opacity, 0.4);
                compare(install.opacity, 0.4);
                waitForRendering(dialog.contentItem);
                grabImage(window.contentItem).save("update-dialog-disabled-" + data.tag + ".png");
                mouseClick(download);
                mouseClick(install);
                compare(findChild(dialog, "downloadUpdateConfirmation").visible, false);
                compare(findChild(dialog, "installUpdateConfirmation").visible, false);
                compare(appUpdater.downloads, 0);
                compare(appUpdater.installs, 0);
                appUpdater.canDownload = true;
                appUpdater.canInstall = true;
                compare(download.opacity, 1);
                compare(install.opacity, 1);
                mouseClick(download);
                tryCompare(findChild(dialog, "downloadUpdateConfirmation"), "opened", true);
                findChild(dialog, "downloadUpdateConfirmation").close();
                dialog.workBusy = true;
                compare(install.enabled, false);
                compare(install.opacity, 0.4);
                appUpdater.busy = true;
                compare(check.enabled, false);
                compare(check.opacity, 0.4);
                compare(appUpdater.downloads, 0);
                compare(appUpdater.installs, 0);
            }
        }
    }
}

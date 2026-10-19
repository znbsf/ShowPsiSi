import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "aboutUpdatesDialog"
    title: "About ShowPsiSi / Updates"
    modal: true
    anchors.centerIn: parent
    width: Math.min(660, parent ? parent.width - 40 : 660)
    height: Math.min(620, parent ? parent.height - 40 : 620)
    property bool workBusy: false
    property bool lightTheme: false
    readonly property color ink: lightTheme ? "#202733" : "#dce1e9"
    readonly property color muted: lightTheme ? "#566171" : "#abb4c2"
    readonly property color surface: lightTheme ? "#ffffff" : "#20232a"
    // The workbench explicitly supplies palette ink, including the disabled
    // group. Preserve enabled contrast while making unavailable actions clear.
    component UpdateAction: Button {
        opacity: enabled ? 1 : 0.4
    }
    closePolicy: Popup.CloseOnEscape
    background: Rectangle { color: dialog.surface; border.color: dialog.lightTheme ? "#6f7b8a" : "#778496"; radius: 6 }
    onClosed: {
        // Dismissal must never leave an invisible network operation running.
        appUpdater.cancel();
        downloadConfirm.close();
        installConfirm.close();
        portableConfirm.close();
    }
    contentItem: ColumnLayout {
        spacing: 10
        Label {
            text: "ShowPsiSi " + appUpdater.currentVersion + " · Qt edition"
            color: dialog.ink; font.bold: true; font.pixelSize: 16
            textFormat: Text.PlainText
        }
        Label {
            objectName: "updateEditionLabel"
            Layout.fillWidth: true
            text: appUpdater.editionLabel
            textFormat: Text.PlainText; wrapMode: Text.Wrap; color: dialog.muted
        }
        TextField {
            objectName: "officialRepositoryUrl"
            Layout.fillWidth: true
            text: appUpdater.repositoryUrl
            readOnly: true; selectByMouse: true
            Accessible.name: "Official GitHub repository URL"
        }
        RowLayout {
            UpdateAction { objectName: "openRepositoryButton"; text: "GitHub repository"; onClicked: appUpdater.openRepository() }
            UpdateAction { objectName: "openReleasesButton"; text: "Release page"; onClicked: appUpdater.openReleases() }
        }
        Label {
            Layout.fillWidth: true
            text: appUpdater.status
            textFormat: Text.PlainText; wrapMode: Text.Wrap
            color: appUpdater.state === "error" ? (dialog.lightTheme ? "#b42929" : "#f48771") : dialog.ink
            Accessible.role: Accessible.StaticText
            Accessible.name: text
        }
        Label {
            Layout.fillWidth: true
            visible: !appUpdater.installerSupported
            text: appUpdater.edition === "portable"
                ? "Portable updates use a ZIP archive. Download in your browser, verify its SHA-256 yourself, then close ShowPsiSi and extract into a new folder. Your current files are never replaced by this app."
                : "This source or unsupported-platform build can check releases. Use the official release page to choose a package for your system; in-app installation is unavailable."
            textFormat: Text.PlainText; wrapMode: Text.Wrap; color: dialog.muted
        }
        ProgressBar {
            objectName: "updateDownloadProgress"
            Layout.fillWidth: true
            visible: appUpdater.busy
            indeterminate: appUpdater.state === "checking"
            from: 0; to: 1; value: appUpdater.progress
        }
        Label {
            text: appUpdater.latestVersion ? "Latest stable release: " + appUpdater.latestVersion : "Release notes"
            color: dialog.ink; font.bold: true; textFormat: Text.PlainText
        }
        ScrollView {
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true
            TextArea {
                objectName: "updateReleaseNotes"
                text: appUpdater.releaseNotes || (appUpdater.latestVersion ? "No release notes were supplied for this release." : "Check for updates to see the latest release notes.")
                textFormat: TextEdit.PlainText
                readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                color: dialog.ink
                background: Rectangle { color: dialog.lightTheme ? "#f5f6f8" : "#181a1f" }
            }
        }
        Label {
            Layout.fillWidth: true
            text: appUpdater.edition === "portable"
                ? "Stable releases only. The ZIP link and expected SHA-256 come from the official GitHub release. This app does not verify browser-downloaded bytes."
                : "Stable releases only. In-app installer downloads are SHA-256 checked against the official GitHub release; browser downloads need manual verification. An independent publisher signature is not enforced."
            color: dialog.muted; textFormat: Text.PlainText; wrapMode: Text.Wrap; font.pixelSize: 11
        }
        Flow {
            Layout.fillWidth: true
            spacing: 6
            UpdateAction {
                objectName: "checkUpdatesButton"
                text: appUpdater.state === "error" || appUpdater.state === "cancelled" ? "Retry check" : "Check for updates"
                enabled: !appUpdater.busy && appUpdater.state !== "launching"
                onClicked: appUpdater.checkForUpdates()
            }
            UpdateAction {
                objectName: "downloadUpdateButton"
                text: "Download installer…"
                visible: appUpdater.edition !== "portable"
                enabled: appUpdater.canDownload
                onClicked: downloadConfirm.open()
            }
            UpdateAction {
                objectName: "installUpdateButton"
                text: "Install and quit…"
                visible: appUpdater.edition !== "portable"
                enabled: appUpdater.canInstall && !dialog.workBusy
                onClicked: installConfirm.open()
            }
            UpdateAction {
                objectName: "portableUpdateButton"
                text: "Portable ZIP…"
                visible: appUpdater.edition === "portable"
                enabled: appUpdater.canOpenPortable
                onClicked: portableConfirm.open()
            }
            UpdateAction {
                objectName: "cancelUpdateButton"
                text: appUpdater.busy ? "Cancel request" : "Close"
                onClicked: appUpdater.busy ? appUpdater.cancel() : dialog.close()
            }
        }
    }
    Dialog {
        id: downloadConfirm
        objectName: "downloadUpdateConfirmation"
        title: "Download this update?"
        anchors.centerIn: parent
        width: Math.min(540, dialog.width - 20)
        modal: true
        standardButtons: Dialog.Yes | Dialog.Cancel
        onAccepted: appUpdater.downloadUpdate()
        contentItem: Label {
            text: "Installed: " + appUpdater.currentVersion + "\nNew version: " + appUpdater.latestVersion +
                "\n\n" + appUpdater.assetName + "\n" + (appUpdater.downloadSize / 1048576).toFixed(1) +
                " MiB from github.com/znbsf/ShowPsiSi\n\nSHA-256:\n" + appUpdater.checksum +
                "\n\nThe installer will not run until you separately choose Install and quit."
            textFormat: Text.PlainText; wrapMode: Text.WrapAnywhere
        }
    }
    Dialog {
        id: portableConfirm
        objectName: "portableUpdateConfirmation"
        title: "Download portable ZIP in your browser?"
        anchors.centerIn: parent
        width: Math.min(540, dialog.width - 20)
        modal: true
        standardButtons: Dialog.NoButton
        contentItem: ColumnLayout {
            spacing: 10
            Label {
                Layout.fillWidth: true
                text: "Current: " + appUpdater.currentVersion + "  →  New: " + appUpdater.latestVersion +
                    "\n\n" + appUpdater.assetName + "\n" + (appUpdater.downloadSize / 1048576).toFixed(1) +
                    " MiB from github.com/znbsf/ShowPsiSi"
                textFormat: Text.PlainText; wrapMode: Text.WrapAnywhere
            }
            Label { text: "Expected SHA-256 (select and copy):"; textFormat: Text.PlainText }
            TextField {
                objectName: "portableExpectedChecksum"
                Layout.fillWidth: true
                text: appUpdater.checksum
                readOnly: true; selectByMouse: true
                Accessible.name: "Expected portable ZIP SHA-256"
            }
            Label {
                Layout.fillWidth: true
                text: "1. Download the ZIP in your browser. This app does not verify that downloaded file.\n2. Compare the saved ZIP's SHA-256 with the value above (for example, using PowerShell Get-FileHash).\n3. Save/export your work and close all ShowPsiSi windows.\n4. Extract into a new folder and run Launch Qt.cmd there. Use the new folder in place of the old one; keep the old copy until you have checked the new version.\n\nNo setup installer or automatic file replacement is used."
                textFormat: Text.PlainText; wrapMode: Text.Wrap
            }
            RowLayout {
                UpdateAction {
                    objectName: "confirmPortableUpdateButton"
                    text: "Open ZIP download"
                    enabled: appUpdater.canOpenPortable
                    onClicked: { portableConfirm.close(); appUpdater.openPortableDownload(); }
                }
                UpdateAction { text: "Go back"; onClicked: portableConfirm.close() }
            }
        }
    }
    Dialog {
        id: installConfirm
        objectName: "installUpdateConfirmation"
        title: "Save your work before installing"
        anchors.centerIn: parent
        width: Math.min(540, dialog.width - 20)
        modal: true
        standardButtons: Dialog.NoButton
        contentItem: ColumnLayout {
            Label {
                Layout.fillWidth: true
                text: "Install ShowPsiSi " + appUpdater.latestVersion + "?\n\nSave or export any work you want to keep first. Choosing Install and quit starts the visible installer and closes this workbench. Unsaved previews and the current workspace will close.\n\nFollow the installer prompts."
                textFormat: Text.PlainText; wrapMode: Text.Wrap
            }
            RowLayout {
                UpdateAction {
                    objectName: "confirmInstallUpdateButton"
                    text: "My work is saved · Install and quit"
                    enabled: appUpdater.canInstall && !dialog.workBusy
                    onClicked: { installConfirm.close(); appUpdater.installUpdate(true); }
                }
                UpdateAction { text: "Go back"; onClicked: installConfirm.close() }
            }
        }
    }
}

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
    closePolicy: Popup.CloseOnEscape
    background: Rectangle { color: dialog.surface; border.color: dialog.lightTheme ? "#6f7b8a" : "#778496"; radius: 6 }
    onClosed: {
        // Dismissal must never leave an invisible network operation running.
        appUpdater.cancel();
        downloadConfirm.close();
        installConfirm.close();
    }
    contentItem: ColumnLayout {
        spacing: 10
        Label {
            text: "ShowPsiSi " + appUpdater.currentVersion + " · Qt edition"
            color: dialog.ink; font.bold: true; font.pixelSize: 16
            textFormat: Text.PlainText
        }
        TextField {
            objectName: "officialRepositoryUrl"
            Layout.fillWidth: true
            text: appUpdater.repositoryUrl
            readOnly: true; selectByMouse: true
            Accessible.name: "Official GitHub repository URL"
        }
        RowLayout {
            Button { objectName: "openRepositoryButton"; text: "GitHub repository"; onClicked: appUpdater.openRepository() }
            Button { objectName: "openReleasesButton"; text: "Release page"; onClicked: appUpdater.openReleases() }
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
            text: "In-app installation requires the installed Windows x64 Qt edition. This build can check releases; use the official release page to download for your system."
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
                text: appUpdater.releaseNotes || "Check for updates to see the latest release notes."
                textFormat: TextEdit.PlainText
                readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                color: dialog.ink
                background: Rectangle { color: dialog.lightTheme ? "#f5f6f8" : "#181a1f" }
            }
        }
        Label {
            Layout.fillWidth: true
            text: "Stable releases only. Downloads are checked against SHA-256 from the official GitHub release. This is an integrity check; an independent publisher signature is not enforced."
            color: dialog.muted; textFormat: Text.PlainText; wrapMode: Text.Wrap; font.pixelSize: 11
        }
        Flow {
            Layout.fillWidth: true
            spacing: 6
            Button {
                objectName: "checkUpdatesButton"
                text: appUpdater.state === "error" || appUpdater.state === "cancelled" ? "Retry check" : "Check for updates"
                enabled: !appUpdater.busy && appUpdater.state !== "launching"
                onClicked: appUpdater.checkForUpdates()
            }
            Button {
                objectName: "downloadUpdateButton"
                text: "Download installer…"
                enabled: appUpdater.canDownload
                onClicked: downloadConfirm.open()
            }
            Button {
                objectName: "installUpdateButton"
                text: "Install and quit…"
                enabled: appUpdater.canInstall && !dialog.workBusy
                onClicked: installConfirm.open()
            }
            Button {
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
                text: "Install ShowPsiSi " + appUpdater.latestVersion + "?\n\nSave or export any work you want to keep first. Choosing Install and quit starts the visible installer and closes this workbench. Unsaved previews and the current workspace will close.\n\nFollow the installer prompts. A runtime prerequisite may ask for Windows administrator approval."
                textFormat: Text.PlainText; wrapMode: Text.Wrap
            }
            RowLayout {
                Button {
                    objectName: "confirmInstallUpdateButton"
                    text: "My work is saved · Install and quit"
                    enabled: appUpdater.canInstall && !dialog.workBusy
                    onClicked: { installConfirm.close(); appUpdater.installUpdate(true); }
                }
                Button { text: "Go back"; onClicked: installConfirm.close() }
            }
        }
    }
}

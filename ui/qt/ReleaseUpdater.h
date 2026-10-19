#pragma once
#include "ReleaseMetadata.h"
#include <QObject>
#include <QPointer>
#include <QTimer>
#include <functional>
#include <memory>
class QNetworkAccessManager;
class QNetworkReply;
class QSaveFile;
class QTemporaryDir;
class QCryptographicHash;
class ReleaseUpdaterTests;

class ReleaseUpdater final : public QObject {
    Q_OBJECT
    Q_PROPERTY(QString currentVersion READ currentVersion CONSTANT)
    Q_PROPERTY(QString repositoryUrl READ repositoryUrl CONSTANT)
    Q_PROPERTY(QString edition READ edition CONSTANT)
    Q_PROPERTY(QString editionLabel READ editionLabel CONSTANT)
    Q_PROPERTY(QString state READ state NOTIFY changed)
    Q_PROPERTY(QString status READ status NOTIFY changed)
    Q_PROPERTY(QString latestVersion READ latestVersion NOTIFY changed)
    Q_PROPERTY(QString releaseNotes READ releaseNotes NOTIFY changed)
    Q_PROPERTY(QString assetName READ assetName NOTIFY changed)
    Q_PROPERTY(QString checksum READ checksum NOTIFY changed)
    Q_PROPERTY(qint64 downloadSize READ downloadSize NOTIFY changed)
    Q_PROPERTY(double progress READ progress NOTIFY changed)
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
    Q_PROPERTY(bool canDownload READ canDownload NOTIFY changed)
    Q_PROPERTY(bool canInstall READ canInstall NOTIFY changed)
    Q_PROPERTY(bool canOpenPortable READ canOpenPortable NOTIFY changed)
    Q_PROPERTY(bool installerSupported READ installerSupported CONSTANT)
public:
    explicit ReleaseUpdater(QObject* parent = nullptr);
    ~ReleaseUpdater() override;
    QString currentVersion() const;
    QString repositoryUrl() const;
    QString edition() const;
    QString editionLabel() const;
    QString state() const { return m_state; }
    QString status() const { return m_status; }
    QString latestVersion() const { return m_release.version; }
    QString releaseNotes() const { return m_release.notes; }
    QString assetName() const { return m_release.assetName; }
    QString checksum() const { return QString::fromLatin1(m_release.sha256.toHex()); }
    qint64 downloadSize() const { return m_release.size; }
    double progress() const;
    bool busy() const;
    bool canDownload() const;
    bool canInstall() const;
    bool canOpenPortable() const;
    bool installerSupported() const { return !m_installRoot.isEmpty(); }
    void setInstallGuard(std::function<bool()> guard) { m_installGuard = std::move(guard); }
    Q_INVOKABLE void checkForUpdates();
    Q_INVOKABLE void downloadUpdate();
    Q_INVOKABLE void cancel();
    // Confirmation is supplied only by the explicit Install-and-quit UI action.
    Q_INVOKABLE void installUpdate(bool savedWorkConfirmed);
    Q_INVOKABLE void openRepository();
    Q_INVOKABLE void openReleases();
    Q_INVOKABLE void openPortableDownload();
signals:
    void changed();
    void installerStarted();
private:
    friend class ReleaseUpdaterTests;
    enum class RequestKind { Metadata, Checksums, Installer };
    QNetworkAccessManager* m_network;
    QPointer<QNetworkReply> m_reply;
    QTimer m_deadline;
    QString m_state = QStringLiteral("idle");
    QString m_status = QStringLiteral("Updates are checked only when you choose Check for updates.");
    ShowPsiSiUpdates::Release m_release;
    RequestKind m_kind = RequestKind::Metadata;
    QByteArray m_body;
    qint64 m_received = 0;
    int m_redirects = 0;
    std::unique_ptr<QTemporaryDir> m_directory;
    std::unique_ptr<QSaveFile> m_file;
    std::unique_ptr<QCryptographicHash> m_hash;
    QString m_installerPath;
    QString m_installRoot;
    bool m_isPortable = false;
    std::function<bool()> m_installGuard;
    void inspectWindowsPackage(const QString& binPath);
    void request(const QUrl& url);
    void consume(QNetworkReply* reply);
    void finished(QNetworkReply* reply);
    void stopRequest();
    void discardDownload();
    void fail(const QString& message);
    void updateState(const QString& state, const QString& message);
    void makeAvailable();
    void openUrl(const QUrl& url);
};

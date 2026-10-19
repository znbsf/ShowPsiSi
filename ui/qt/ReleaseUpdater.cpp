#include "ReleaseUpdater.h"
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDesktopServices>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QProcess>
#include <QSaveFile>
#include <QStandardPaths>
#include <QTemporaryDir>

#ifndef SHOWPSISI_VERSION
#define SHOWPSISI_VERSION "0.1.0"
#endif
using namespace ShowPsiSiUpdates;

ReleaseUpdater::ReleaseUpdater(QObject* parent) : QObject(parent), m_network(new QNetworkAccessManager(this)) {
    // No API token, endpoint setting, background poll or environment override.
    m_deadline.setSingleShot(true);
    connect(&m_deadline, &QTimer::timeout, this, [this] {
        fail(QStringLiteral("Update request timed out. Check your connection and retry."));
    });
#if defined(Q_OS_WIN) && defined(Q_PROCESSOR_X86_64)
    inspectWindowsPackage(QCoreApplication::applicationDirPath());
#endif
}
void ReleaseUpdater::inspectWindowsPackage(const QString& binPath) {
    m_installRoot.clear(); m_isPortable = false;
    const QDir bin(binPath);
    QFile marker(bin.filePath("showpsisi-portable.json"));
    if (marker.open(QIODevice::ReadOnly) && marker.size() <= 4096) {
        const auto object = QJsonDocument::fromJson(marker.readAll()).object();
        if (object.value("schema_version").toInt() == 1 && object.value("resource_root").toString() == ".." &&
            object.value("scope").toString() == "qt-core" && QFileInfo(bin.filePath("../api/tools.json")).isFile())
        {
            const QString root = QDir::cleanPath(bin.absoluteFilePath(".."));
            QFile installation(root + "/showpsisi-installation.json");
            // The same payload backs both distributions. An absent installer
            // marker means portable; a malformed existing marker fails closed.
            m_isPortable = !QFileInfo::exists(installation.fileName());
            if (installation.open(QIODevice::ReadOnly) && installation.size() <= 16384) {
                const auto installed = QJsonDocument::fromJson(installation.readAll()).object();
                if (installed.value("schema_version").toInt() == 1 &&
                    installed.value("app_id").toString() == "{13C6E0A2-B226-4BAA-A218-8DD167D78D4C}" &&
                    installed.value("installer").toString() == "inno" && installed.value("frontend").toString() == "qt" &&
                    installed.value("channel").toString() == "stable" && installed.value("version").toString() == currentVersion())
                    m_installRoot = root;
            }
        }
    }
}
ReleaseUpdater::~ReleaseUpdater() { stopRequest(); discardDownload(); }
QString ReleaseUpdater::currentVersion() const { return QStringLiteral(SHOWPSISI_VERSION); }
QString ReleaseUpdater::repositoryUrl() const { return ShowPsiSiUpdates::repositoryUrl(); }
QString ReleaseUpdater::edition() const { return installerSupported() ? "installed" : m_isPortable ? "portable" : "source"; }
QString ReleaseUpdater::editionLabel() const {
    if (installerSupported()) return "Windows x64 Qt · installed edition";
    if (m_isPortable) return "Windows x64 Qt · portable edition (no installation)";
#if defined(Q_OS_WIN) && defined(Q_PROCESSOR_X86_64)
    return "Qt source build or unrecognized package";
#else
    return "Qt non-Windows or unsupported-platform build";
#endif
}
bool ReleaseUpdater::busy() const { return m_state == "checking" || m_state == "downloading"; }
bool ReleaseUpdater::canDownload() const {
    return installerSupported() && m_release.kind == PackageKind::Installer && !busy() && m_state != "ready" && m_state != "launching" &&
           m_release.sha256.size() == 32 && isNewerVersion(m_release.version, currentVersion());
}
bool ReleaseUpdater::canInstall() const { return installerSupported() && m_release.kind == PackageKind::Installer && m_state == "ready" && !m_installerPath.isEmpty(); }
bool ReleaseUpdater::canOpenPortable() const {
    return edition() == "portable" && m_state == "available" && m_release.kind == PackageKind::Portable &&
           m_release.sha256.size() == 32 && !m_release.assetUrl.isEmpty() && isNewerVersion(m_release.version, currentVersion());
}
double ReleaseUpdater::progress() const { return m_release.size > 0 ? double(m_received) / double(m_release.size) : 0; }
void ReleaseUpdater::updateState(const QString& state, const QString& message) { m_state = state; m_status = message; emit changed(); }
void ReleaseUpdater::stopRequest() {
    m_deadline.stop();
    if (m_reply) {
        auto reply = m_reply.data(); m_reply = nullptr;
        reply->disconnect(this); reply->abort(); reply->deleteLater();
    }
}
void ReleaseUpdater::discardDownload() {
    if (m_file) m_file->cancelWriting();
    m_file.reset(); m_hash.reset(); m_installerPath.clear(); m_directory.reset(); m_received = 0;
}
void ReleaseUpdater::fail(const QString& message) {
    stopRequest(); discardDownload(); m_body.clear();
    updateState("error", message);
}
void ReleaseUpdater::cancel() {
    if (!busy()) return;
    stopRequest(); discardDownload(); m_body.clear();
    // A cancelled checksum fetch must never make an unverified candidate usable.
    updateState("cancelled", "Update request cancelled. No installer was started.");
}
void ReleaseUpdater::checkForUpdates() {
    if (busy() || m_state == "launching") return;
    discardDownload(); m_release = {}; m_body.clear(); m_redirects = 0;
    m_kind = RequestKind::Metadata;
    updateState("checking", "Checking the official GitHub repository for a stable release…");
    m_deadline.start(30000);
    request(latestReleaseApi());
}
void ReleaseUpdater::request(const QUrl& url) {
    QNetworkRequest request(url);
    request.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::ManualRedirectPolicy);
    request.setAttribute(QNetworkRequest::CacheLoadControlAttribute, QNetworkRequest::AlwaysNetwork);
    request.setRawHeader("User-Agent", QByteArray("ShowPsiSi/") + SHOWPSISI_VERSION);
    request.setRawHeader("Accept", m_kind == RequestKind::Metadata ? "application/vnd.github+json" : "application/octet-stream");
    if (m_kind == RequestKind::Metadata) request.setRawHeader("X-GitHub-Api-Version", "2022-11-28");
    request.setTransferTimeout(15000);
    auto reply = m_network->get(request);
    m_reply = reply;
    reply->setReadBufferSize(256 * 1024);
    connect(reply, &QNetworkReply::readyRead, this, [this, reply] { if (m_reply == reply) consume(reply); });
    connect(reply, &QNetworkReply::finished, this, [this, reply] { if (m_reply == reply) finished(reply); });
    // Qt's normal certificate verification remains enabled; sslErrors is never ignored.
}
void ReleaseUpdater::consume(QNetworkReply* reply) {
    if (reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt() != 200) {
        reply->readAll(); // Redirect/error response bodies never become release data.
        return;
    }
    const qint64 limit = m_kind == RequestKind::Installer ? m_release.size :
                        m_kind == RequestKind::Checksums ? MaxChecksumBytes : MaxMetadataBytes;
    while (reply->bytesAvailable() > 0) {
        const QByteArray chunk = reply->read(64 * 1024);
        if (chunk.isEmpty()) break;
        if (m_received > limit - chunk.size()) { fail("Update response exceeded its permitted size."); return; }
        m_received += chunk.size();
        if (m_kind == RequestKind::Installer) {
            if (!m_file || m_file->write(chunk) != chunk.size()) { fail("Could not write the installer. Check free disk space and retry."); return; }
            m_hash->addData(chunk);
        } else m_body += chunk;
    }
    if (m_kind == RequestKind::Installer) emit changed();
}
void ReleaseUpdater::finished(QNetworkReply* reply) {
    consume(reply);
    if (m_reply != reply) return; // consume may fail and invalidate this operation.
    m_reply = nullptr;
    const int status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
    const auto error = reply->error();
    const QUrl redirect = reply->attribute(QNetworkRequest::RedirectionTargetAttribute).toUrl();
    const QUrl responseUrl = reply->url();
    reply->deleteLater();
    if (status >= 300 && status < 400 && !redirect.isEmpty()) {
        const auto target = responseUrl.resolved(redirect);
        if (m_kind == RequestKind::Metadata || !isAllowedAssetRedirect(target) || ++m_redirects > 3) {
            fail("Update redirect was not an approved HTTPS GitHub release-asset destination."); return;
        }
        request(target); return;
    }
    if (m_kind == RequestKind::Metadata && status == 404) {
        m_deadline.stop(); updateState("no-release", "No published stable release is available yet. Try again later or open the release page."); return;
    }
    if (status == 403 || status == 429) { fail("GitHub refused or rate-limited this request. Retry later or open the official release page."); return; }
    if (error != QNetworkReply::NoError || status != 200) {
        fail(QString("Update request failed (HTTP %1, network error %2). Check your connection and retry.").arg(status).arg(int(error))); return;
    }
    if (m_kind == RequestKind::Metadata) {
        const auto parsed = parseRelease(m_body, currentVersion(), m_isPortable ? PackageKind::Portable : PackageKind::Installer);
        m_body.clear(); m_received = 0;
        if (parsed.status == MetadataStatus::Rejected) { fail(parsed.error); return; }
        m_release = parsed.release;
        if (parsed.status == MetadataStatus::UpToDate) {
            m_deadline.stop(); updateState("up-to-date", "No newer stable version is available. Current version: " + currentVersion() + "."); return;
        }
        if (m_release.sha256.isEmpty()) {
            m_kind = RequestKind::Checksums; m_redirects = 0;
            updateState("checking", "Checking the official release's package checksum…");
            request(m_release.checksumsUrl); return;
        }
        makeAvailable(); return;
    }
    if (m_kind == RequestKind::Checksums) {
        QString checksumError;
        m_release.sha256 = parseChecksum(m_body, m_release.assetName, &checksumError);
        m_body.clear(); m_received = 0;
        if (m_release.sha256.isEmpty()) { fail(checksumError); return; }
        makeAvailable(); return;
    }
    if (!m_file || !m_hash || m_received != m_release.size || m_hash->result() != m_release.sha256) {
        fail("Installer size or SHA-256 verification failed. The incomplete download was removed; retry from the official release."); return;
    }
    if (!m_file->commit()) { fail("Could not finalize the verified installer. Check free disk space and retry."); return; }
    m_file.reset(); m_hash.reset(); m_deadline.stop();
    updateState("ready", "Installer downloaded and SHA-256 verified. Save or export your work before choosing Install and quit.");
}
void ReleaseUpdater::makeAvailable() {
    m_deadline.stop();
    updateState("available", "Version " + m_release.version + " is available. Review the release notes before downloading.");
}
void ReleaseUpdater::downloadUpdate() {
    if (!canDownload()) return;
    discardDownload(); m_body.clear(); m_redirects = 0;
    const QString cache = QStandardPaths::writableLocation(QStandardPaths::CacheLocation);
    if (cache.isEmpty() || !QDir().mkpath(cache)) { fail("The update cache directory is not writable."); return; }
    m_directory = std::make_unique<QTemporaryDir>(cache + "/update-XXXXXX");
    if (!m_directory->isValid()) { fail("Could not create a private update download directory."); return; }
    m_installerPath = m_directory->filePath(m_release.assetName);
    m_file = std::make_unique<QSaveFile>(m_installerPath);
    m_file->setDirectWriteFallback(false);
    if (!m_file->open(QIODevice::WriteOnly)) { fail("Could not create the installer download."); return; }
    m_hash = std::make_unique<QCryptographicHash>(QCryptographicHash::Sha256);
    m_kind = RequestKind::Installer;
    updateState("downloading", "Downloading the Windows x64 installer…");
    m_deadline.start(10 * 60 * 1000);
    request(m_release.assetUrl);
}
void ReleaseUpdater::installUpdate(bool savedWorkConfirmed) {
    if (!savedWorkConfirmed || !canInstall()) return;
    if (m_installGuard && !m_installGuard()) {
        m_status = "Wait for all analysis, export and other operations to finish before installing.";
        emit changed(); return;
    }
    // Revalidate on the user's confirmation, including staged-file replacement.
    QFile installer(m_installerPath);
    QCryptographicHash hash(QCryptographicHash::Sha256);
    if (!installer.open(QIODevice::ReadOnly) || installer.size() != m_release.size ||
        !hash.addData(&installer) || hash.result() != m_release.sha256) {
        fail("The downloaded installer changed or is unreadable. Download it again before installing."); return;
    }
    installer.close();
#if defined(Q_OS_WIN) && defined(Q_PROCESSOR_X86_64)
    const QStringList arguments = {"/UPDATE", "/DIR=" + QDir::toNativeSeparators(m_installRoot), "/NORESTART"};
    if (!QProcess::startDetached(m_installerPath, arguments, m_installRoot)) {
        m_status = "The installer could not be started. Your workbench remains open; retry when ready.";
        emit changed(); return;
    }
    // Keep the validated executable while the detached installer reads it. It
    // lives in the app cache and is never automatically run on a later launch.
    m_directory->setAutoRemove(false);
    updateState("launching", "Installer started. Closing ShowPsiSi as you requested; follow the installation wizard.");
    emit installerStarted();
#else
    m_status = "In-app installation is supported only by the installed Windows x64 Qt edition.";
    emit changed();
#endif
}
void ReleaseUpdater::openUrl(const QUrl& url) {
    if (!QDesktopServices::openUrl(url)) { m_status = "The browser could not open the link. Copy the official repository URL shown above."; emit changed(); }
}
void ReleaseUpdater::openRepository() { openUrl(QUrl(repositoryUrl())); }
void ReleaseUpdater::openReleases() { openUrl(QUrl(releasesUrl())); }

void ReleaseUpdater::openPortableDownload() {
    if (!canOpenPortable()) return;
    // The browser owns this download. Do not claim verification of its bytes,
    // touch the current application directory, or offer installer migration.
    openUrl(m_release.assetUrl);
}

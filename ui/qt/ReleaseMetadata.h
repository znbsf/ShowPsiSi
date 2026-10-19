#pragma once
#include <QByteArray>
#include <QString>
#include <QUrl>

namespace ShowPsiSiUpdates {
inline constexpr qint64 MaxInstallerBytes = 1024LL * 1024 * 1024;
inline constexpr qint64 MaxMetadataBytes = 2LL * 1024 * 1024;
inline constexpr qint64 MaxChecksumBytes = 64LL * 1024;

QString repositoryUrl();
QString releasesUrl();
QUrl latestReleaseApi();
bool isStableVersion(const QString& version);
bool isNewerVersion(const QString& candidate, const QString& current);
bool isAllowedAssetRedirect(const QUrl& url);

struct Release {
    QString version;
    QString tag;
    QString notes;
    QString assetName;
    QUrl pageUrl;
    QUrl assetUrl;
    QUrl checksumsUrl;
    QByteArray sha256;
    qint64 size = 0;
};
enum class MetadataStatus { UpdateAvailable, UpToDate, Rejected };
struct MetadataResult {
    MetadataStatus status = MetadataStatus::Rejected;
    Release release;
    QString error;
};
MetadataResult parseRelease(const QByteArray& json, const QString& currentVersion);
// A checksum file is only trusted when fetched through this release's validated
// official asset URL. It is integrity evidence, not independent publisher signing.
QByteArray parseChecksum(const QByteArray& text, const QString& assetName, QString* error);
}

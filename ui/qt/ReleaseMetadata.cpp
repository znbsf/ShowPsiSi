#include "ReleaseMetadata.h"
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QStringList>
#include <array>
#include <cmath>
#include <optional>

namespace ShowPsiSiUpdates {
namespace {
struct Version { std::array<quint64, 3> numbers; QString prerelease; };
std::optional<Version> parseVersion(const QString& text) {
    // SemVer 2.0, including numeric identifier leading-zero restrictions.
    static const QRegularExpression pattern(QStringLiteral(
        "\\A(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)"
        "(?:-([0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*))?"
        "(?:\\+([0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*))?\\z"));
    if (text.size() > 128) return std::nullopt;
    const auto match = pattern.match(text);
    if (!match.hasMatch()) return std::nullopt;
    Version result;
    for (int i = 0; i < 3; ++i) {
        bool ok = false;
        result.numbers[i] = match.captured(i + 1).toULongLong(&ok);
        if (!ok) return std::nullopt;
    }
    result.prerelease = match.captured(4);
    for (const auto& part : result.prerelease.split('.')) {
        if (part.size() > 1 && part.front() == '0' &&
            QRegularExpression(QStringLiteral("^[0-9]+$")).match(part).hasMatch()) return std::nullopt;
    }
    return result;
}
bool httpsUrl(const QUrl& url) {
    return url.isValid() && url.scheme() == QStringLiteral("https") &&
           url.userInfo().isEmpty() && (url.port(-1) == -1 || url.port() == 443) &&
           !url.hasFragment();
}
bool exactUrl(const QString& text, const QString& expected) {
    const QUrl url(text, QUrl::StrictMode);
    return httpsUrl(url) && text == expected && url.toString(QUrl::FullyEncoded) == expected;
}
QByteArray digest(const QJsonValue& value, bool* malformed) {
    *malformed = false;
    if (value.isNull() || value.isUndefined()) return {};
    if (!value.isString()) { *malformed = true; return {}; }
    const QString text = value.toString();
    // GitHub currently emits sha256:<hex>. Never silently ignore a supplied
    // malformed or different-algorithm digest and downgrade to another source.
    static const QRegularExpression pattern(QStringLiteral("\\Asha256:([0-9a-fA-F]{64})\\z"));
    const auto match = pattern.match(text);
    if (!match.hasMatch()) { *malformed = true; return {}; }
    return QByteArray::fromHex(match.captured(1).toLatin1());
}
}
QString repositoryUrl() { return QStringLiteral("https://github.com/znbsf/ShowPsiSi"); }
QString releasesUrl() { return repositoryUrl() + QStringLiteral("/releases"); }
QUrl latestReleaseApi() { return QUrl(QStringLiteral("https://api.github.com/repos/znbsf/ShowPsiSi/releases/latest")); }
bool isStableVersion(const QString& version) {
    const auto parsed = parseVersion(version);
    // Release artifact names deliberately exclude build metadata as well.
    return parsed && parsed->prerelease.isEmpty() && !version.contains('+');
}
bool isNewerVersion(const QString& candidate, const QString& current) {
    const auto left = parseVersion(candidate), right = parseVersion(current);
    if (!left || !right || !isStableVersion(candidate)) return false;
    if (left->numbers != right->numbers) return left->numbers > right->numbers;
    return !right->prerelease.isEmpty();
}
bool isAllowedAssetRedirect(const QUrl& url) {
    if (!httpsUrl(url)) return false;
    // Redirects are manually inspected before issuing the next request. GitHub
    // serves release assets through this HTTPS CDN with expiring query tokens.
    return url.host() == QStringLiteral("release-assets.githubusercontent.com") ||
           url.host() == QStringLiteral("objects.githubusercontent.com");
}
MetadataResult parseRelease(const QByteArray& json, const QString& currentVersion) {
    MetadataResult out;
    auto reject = [&](const QString& error) { out.error = error; return out; };
    if (!parseVersion(currentVersion)) return reject(QStringLiteral("The installed version is invalid; use the official release page."));
    if (json.isEmpty() || json.size() > MaxMetadataBytes) return reject(QStringLiteral("Release metadata is empty or too large."));
    QJsonParseError jsonError;
    const auto document = QJsonDocument::fromJson(json, &jsonError);
    if (jsonError.error != QJsonParseError::NoError || !document.isObject())
        return reject(QStringLiteral("GitHub returned malformed release metadata."));
    const auto object = document.object();
    if (!object.value("draft").isBool() || !object.value("prerelease").isBool() ||
        object.value("draft").toBool() || object.value("prerelease").toBool())
        return reject(QStringLiteral("Only published stable releases are eligible for updates."));
    const QString tag = object.value("tag_name").toString();
    if (!tag.startsWith('v') || !isStableVersion(tag.mid(1)))
        return reject(QStringLiteral("Release tag is not a stable vMAJOR.MINOR.PATCH version."));
    out.release.version = tag.mid(1);
    out.release.tag = tag;
    const QString page = repositoryUrl() + "/releases/tag/" + tag;
    if (!exactUrl(object.value("html_url").toString(), page))
        return reject(QStringLiteral("Release page is outside the official repository."));
    out.release.pageUrl = QUrl(page);
    if (!object.value("body").isString() && !object.value("body").isNull())
        return reject(QStringLiteral("Release notes have an invalid type."));
    out.release.notes = object.value("body").toString().left(100000);
    if (!isNewerVersion(out.release.version, currentVersion)) {
        out.status = MetadataStatus::UpToDate;
        return out;
    }
    if (!object.value("assets").isArray()) return reject(QStringLiteral("Release assets are missing."));
    out.release.assetName = "ShowPsiSi-" + out.release.version + "-windows-x64-setup.exe";
    const QString assetBase = repositoryUrl() + "/releases/download/" + tag + "/";
    int installers = 0, checksumFiles = 0;
    for (const auto& value : object.value("assets").toArray()) {
        if (!value.isObject()) return reject(QStringLiteral("Malformed release asset entry."));
        const auto asset = value.toObject();
        const QString name = asset.value("name").toString();
        if (name != out.release.assetName && name != "SHA256SUMS") continue;
        if (!exactUrl(asset.value("browser_download_url").toString(), assetBase + name))
            return reject(QStringLiteral("Release asset URL is outside the expected official release."));
        if (asset.value("state").toString() != "uploaded")
            return reject(QStringLiteral("Release asset has not finished uploading."));
        const auto sizeValue = asset.value("size");
        const double size = sizeValue.toDouble(-1);
        const qint64 limit = name == "SHA256SUMS" ? MaxChecksumBytes : MaxInstallerBytes;
        if (!sizeValue.isDouble() || !std::isfinite(size) || std::floor(size) != size || size <= 0 || size > double(limit))
            return reject(QStringLiteral("Release asset has an invalid or excessive size."));
        if (name == "SHA256SUMS") {
            ++checksumFiles;
            out.release.checksumsUrl = QUrl(assetBase + name);
        } else {
            ++installers;
            out.release.assetUrl = QUrl(assetBase + name);
            out.release.size = qint64(size);
            bool malformed = false;
            out.release.sha256 = digest(asset.value("digest"), &malformed);
            if (malformed) return reject(QStringLiteral("Release installer SHA-256 digest is malformed."));
        }
    }
    if (installers != 1 || checksumFiles > 1)
        return reject(QStringLiteral("Release must contain exactly one matching Windows x64 installer and no duplicate checksum files."));
    if (out.release.sha256.isEmpty() && out.release.checksumsUrl.isEmpty())
        return reject(QStringLiteral("Release provides no trusted SHA-256 checksum. Installation is blocked."));
    out.status = MetadataStatus::UpdateAvailable;
    return out;
}
QByteArray parseChecksum(const QByteArray& text, const QString& assetName, QString* error) {
    auto reject = [&](const QString& message) { if (error) *error = message; return QByteArray(); };
    if (error) error->clear();
    if (text.isEmpty() || text.size() > MaxChecksumBytes || text.contains('\0'))
        return reject(QStringLiteral("Release checksum file is empty or invalid."));
    static const QRegularExpression linePattern(QStringLiteral("^([0-9a-fA-F]{64}) [ *]([^\\r\\n]+)$"));
    QByteArray result;
    for (auto line : QString::fromUtf8(text).split('\n')) {
        if (line.endsWith('\r')) line.chop(1);
        if (line.isEmpty()) continue;
        const auto match = linePattern.match(line);
        if (!match.hasMatch()) return reject(QStringLiteral("Release checksum file has a malformed line."));
        if (match.captured(2) == assetName) {
            if (!result.isEmpty()) return reject(QStringLiteral("Release checksum file contains a duplicate installer entry."));
            result = QByteArray::fromHex(match.captured(1).toLatin1());
        }
    }
    if (result.isEmpty()) return reject(QStringLiteral("Release checksum file does not identify the exact installer."));
    return result;
}
}

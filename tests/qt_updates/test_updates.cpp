#include "ReleaseMetadata.h"
#include "ReleaseUpdater.h"
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QQueue>
#include <QSignalSpy>
#include <QStandardPaths>
#include <QTemporaryDir>
#include <QtTest>
#include <cstring>
using namespace ShowPsiSiUpdates;
namespace {
const QByteArray installerBytes("This is a fixture, not executable installer code.\n");
QJsonObject releaseObject(const QString& version = "0.2.0", bool withDigest = true) {
    const QString base = repositoryUrl() + "/releases/download/v" + version + "/";
    const QString name = "ShowPsiSi-" + version + "-windows-x64-setup.exe";
    QJsonObject installer{{"name", name}, {"state", "uploaded"}, {"size", installerBytes.size()},
                          {"browser_download_url", base + name}};
    if (withDigest) installer["digest"] = "sha256:" + QString::fromLatin1(QCryptographicHash::hash(installerBytes, QCryptographicHash::Sha256).toHex());
    return {{"tag_name", "v" + version}, {"draft", false}, {"prerelease", false},
            {"html_url", repositoryUrl() + "/releases/tag/v" + version},
            {"body", "Fixture release notes <script> must stay plain text."},
            {"assets", QJsonArray{installer, QJsonObject{{"name", "SHA256SUMS"}, {"state", "uploaded"}, {"size", 120}, {"browser_download_url", base + "SHA256SUMS"}}}}};
}
QByteArray releaseJson(const QString& version = "0.2.0", bool digest = true) { return QJsonDocument(releaseObject(version, digest)).toJson(); }
struct FixtureResponse { QByteArray body; int status = 200; QUrl redirect; bool held = false; QNetworkReply::NetworkError error = QNetworkReply::NoError; };
class FixtureReply final : public QNetworkReply {
public:
    FixtureReply(const QNetworkRequest& request, FixtureResponse response, QObject* parent)
        : QNetworkReply(parent), fixture(std::move(response)) {
        setRequest(request); setUrl(request.url()); setOperation(QNetworkAccessManager::GetOperation);
        setAttribute(QNetworkRequest::HttpStatusCodeAttribute, fixture.status);
        if (!fixture.redirect.isEmpty()) setAttribute(QNetworkRequest::RedirectionTargetAttribute, fixture.redirect);
        open(QIODevice::ReadOnly | QIODevice::Unbuffered);
        if (!fixture.held) QTimer::singleShot(0, this, [this] { publish(); });
    }
    void abort() override { aborted = true; setError(OperationCanceledError, "fixture cancelled"); setFinished(true); emit finished(); }
    qint64 bytesAvailable() const override { return available.size() - position + QIODevice::bytesAvailable(); }
    void publish(bool terminal = true) {
        available += fixture.body;
        emit readyRead();
        if (terminal && !aborted) {
            if (fixture.error != NoError) setError(fixture.error, "fixture network failure");
            setFinished(true); emit finished();
        }
    }
    bool aborted = false;
protected:
    qint64 readData(char* data, qint64 count) override {
        const qint64 copied = qMin(count, qint64(available.size()) - position);
        if (copied <= 0) return -1;
        std::memcpy(data, available.constData() + position, size_t(copied)); position += copied; return copied;
    }
private:
    FixtureResponse fixture;
    QByteArray available;
    qint64 position = 0;
};
class FixtureNetwork final : public QNetworkAccessManager {
public:
    using QNetworkAccessManager::QNetworkAccessManager;
    QQueue<FixtureResponse> responses;
    QList<QNetworkRequest> requests;
    QPointer<FixtureReply> last;
protected:
    QNetworkReply* createRequest(Operation operation, const QNetworkRequest& request, QIODevice*) override {
        Q_ASSERT(operation == GetOperation);
        requests.append(request);
        auto response = responses.isEmpty() ? FixtureResponse{{}, 500} : responses.dequeue();
        last = new FixtureReply(request, response, this); return last;
    }
};
}
class ReleaseUpdaterTests final : public QObject {
    Q_OBJECT
    FixtureNetwork* attach(ReleaseUpdater& updater) {
        delete updater.m_network;
        auto network = new FixtureNetwork(&updater); updater.m_network = network;
        // Test code can inspect internals but no fixture endpoint, launch hook or
        // environment switch is compiled into the production application.
        updater.m_installRoot = QDir::tempPath();
        return network;
    }
private slots:
    void initTestCase() { QStandardPaths::setTestModeEnabled(true); }
    void stableVersions_data() {
        QTest::addColumn<QString>("version"); QTest::addColumn<bool>("valid");
        for (const auto& version : {"0.0.0", "0.1.0", "1.10.100", "99.999.9999"}) QTest::newRow(version) << QString(version) << true;
        for (const auto& version : {"1.0", "01.0.0", "1.02.0", "1.0.03", "1.0.0-beta", "1.0.0+build", "v1.0.0", "1.0.0\n", " 1.0.0", "1.0.0/evil", "18446744073709551616.0.0"}) QTest::newRow(version) << QString(version) << false;
    }
    void stableVersions() { QFETCH(QString, version); QFETCH(bool, valid); QCOMPARE(isStableVersion(version), valid); }
    void versionComparisonPreventsDowngrade() {
        QVERIFY(isNewerVersion("1.10.0", "1.9.9"));
        QVERIFY(isNewerVersion("1.0.0", "1.0.0-rc.1"));
        QVERIFY(!isNewerVersion("1.0.0", "1.0.0+local"));
        QVERIFY(!isNewerVersion("1.0.0", "1.0.1"));
        QVERIFY(!isNewerVersion("1.0.0", "1.0.0"));
        QVERIFY(!isNewerVersion("1.1.0-beta", "1.0.0"));
        QVERIFY(!isNewerVersion("1.1.0", "1.0.0-01"));
    }
    void metadataRequiresExactPlatformAndOrigin() {
        auto object = releaseObject();
        auto parsed = parseRelease(QJsonDocument(object).toJson(), "0.1.0");
        QCOMPARE(parsed.status, MetadataStatus::UpdateAvailable);
        QCOMPARE(parsed.release.assetName, QString("ShowPsiSi-0.2.0-windows-x64-setup.exe"));
        QCOMPARE(parsed.release.sha256.size(), 32);
        for (const auto& url : {"http://github.com/znbsf/ShowPsiSi/releases/download/v0.2.0/ShowPsiSi-0.2.0-windows-x64-setup.exe",
            "https://evil.example/ShowPsiSi-0.2.0-windows-x64-setup.exe",
            "https://github.com/attacker/ShowPsiSi/releases/download/v0.2.0/ShowPsiSi-0.2.0-windows-x64-setup.exe",
            "https://github.com/znbsf/ShowPsiSi/releases/download/v0.1.0/ShowPsiSi-0.2.0-windows-x64-setup.exe",
            "https://github.com/znbsf/ShowPsiSi/releases/download/v0.2.0/ShowPsiSi-0.2.0-windows-x64-setup.exe?token=x",
            "https://github.com/znbsf/ShowPsiSi/releases/download/v0.2.0/ShowPsiSi-0.2.0-windows-x64-setup.exe#fragment"}) {
            auto assets = object["assets"].toArray(); auto asset = assets[0].toObject(); asset["browser_download_url"] = url; assets[0] = asset; object["assets"] = assets;
            QCOMPARE(parseRelease(QJsonDocument(object).toJson(), "0.1.0").status, MetadataStatus::Rejected);
        }
        object = releaseObject(); auto assets = object["assets"].toArray(); auto asset = assets[0].toObject(); asset["name"] = "ShowPsiSi-0.2.0-windows-arm64-setup.exe"; assets[0] = asset; object["assets"] = assets;
        QCOMPARE(parseRelease(QJsonDocument(object).toJson(), "0.1.0").status, MetadataStatus::Rejected);
    }
    void malformedReleaseMetadataFailsClosed() {
        for (const QByteArray input : {QByteArray(), QByteArray("{"), QByteArray("[]"), QByteArray("null")}) QCOMPARE(parseRelease(input, "0.1.0").status, MetadataStatus::Rejected);
        for (const auto& key : {"draft", "prerelease"}) {
            auto object = releaseObject(); object[key] = true;
            QCOMPARE(parseRelease(QJsonDocument(object).toJson(), "0.1.0").status, MetadataStatus::Rejected);
            object[key] = "false";
            QCOMPARE(parseRelease(QJsonDocument(object).toJson(), "0.1.0").status, MetadataStatus::Rejected);
        }
        auto object = releaseObject(); object["tag_name"] = "v0.2.0-rc.1";
        QCOMPARE(parseRelease(QJsonDocument(object).toJson(), "0.1.0").status, MetadataStatus::Rejected);
        object = releaseObject(); object["html_url"] = "https://github.com/evil/release";
        QCOMPARE(parseRelease(QJsonDocument(object).toJson(), "0.1.0").status, MetadataStatus::Rejected);
        object = releaseObject(); object["body"] = QJsonObject{{"html", "bad"}};
        QCOMPARE(parseRelease(QJsonDocument(object).toJson(), "0.1.0").status, MetadataStatus::Rejected);
        QCOMPARE(parseRelease(releaseJson("0.1.0"), "0.1.0").status, MetadataStatus::UpToDate);
        QCOMPARE(parseRelease(releaseJson("0.1.0"), "9.1.0").status, MetadataStatus::UpToDate);
    }
    void invalidAssetSizeDigestAndDuplicates() {
        for (QJsonValue size : {QJsonValue(0), QJsonValue(-1), QJsonValue(1.5), QJsonValue(double(MaxInstallerBytes + 1)), QJsonValue("100")}) {
            auto object = releaseObject(); auto assets = object["assets"].toArray(); auto asset = assets[0].toObject(); asset["size"] = size; assets[0] = asset; object["assets"] = assets;
            QCOMPARE(parseRelease(QJsonDocument(object).toJson(), "0.1.0").status, MetadataStatus::Rejected);
        }
        for (QString digest : QStringList{"sha256:bad", "sha1:" + QString(64, '0'), "sha256:" + QString(64, '0') + "\n", QString()}) {
            auto object = releaseObject(); auto assets = object["assets"].toArray(); auto asset = assets[0].toObject(); asset["digest"] = digest; assets[0] = asset; object["assets"] = assets;
            QCOMPARE(parseRelease(QJsonDocument(object).toJson(), "0.1.0").status, MetadataStatus::Rejected);
        }
        auto object = releaseObject(); auto assets = object["assets"].toArray(); assets.append(assets[0]); object["assets"] = assets;
        QCOMPARE(parseRelease(QJsonDocument(object).toJson(), "0.1.0").status, MetadataStatus::Rejected);
        object = releaseObject("0.2.0", false); assets = object["assets"].toArray(); assets.removeLast(); object["assets"] = assets;
        QCOMPARE(parseRelease(QJsonDocument(object).toJson(), "0.1.0").status, MetadataStatus::Rejected);
    }
    void checksumParserExactNamesAndDuplicates() {
        const QByteArray hash = QCryptographicHash::hash(installerBytes, QCryptographicHash::Sha256);
        const QString name = "ShowPsiSi-0.2.0-windows-x64-setup.exe";
        const QByteArray line = hash.toHex() + "  " + name.toUtf8() + "\n";
        QString error;
        QCOMPARE(parseChecksum(line, name, &error), hash);
        QCOMPARE(parseChecksum(hash.toHex() + " *" + name.toUtf8() + "\r\n", name, &error), hash);
        QVERIFY(parseChecksum(line + line, name, &error).isEmpty());
        QVERIFY(parseChecksum(line, "different.exe", &error).isEmpty());
        QVERIFY(parseChecksum("invalid line\n" + line, name, &error).isEmpty());
        QVERIFY(parseChecksum(QByteArray(MaxChecksumBytes + 1, 'x'), name, &error).isEmpty());
    }
    void redirectsRestrictedToHttpsCdn() {
        QVERIFY(isAllowedAssetRedirect(QUrl("https://release-assets.githubusercontent.com/a?token=fixture")));
        QVERIFY(isAllowedAssetRedirect(QUrl("https://objects.githubusercontent.com/a")));
        for (const auto& url : {"http://release-assets.githubusercontent.com/a", "https://release-assets.githubusercontent.com.evil/a", "https://evil.example/a", "https://user@objects.githubusercontent.com/a", "https://objects.githubusercontent.com:444/a", "https://objects.githubusercontent.com/a#fragment", "file:///tmp/a"}) QVERIFY(!isAllowedAssetRedirect(QUrl(url)));
    }
    void networkCheckAndDownloadAreSeparate() {
        ReleaseUpdater updater; auto network = attach(updater);
        QCOMPARE(network->requests.size(), 0);
        network->responses.enqueue({releaseJson()});
        updater.checkForUpdates(); updater.checkForUpdates();
        QTRY_COMPARE(updater.state(), QString("available"));
        QCOMPARE(network->requests.size(), 1);
        QCOMPARE(network->requests[0].url(), latestReleaseApi());
        QCOMPARE(network->requests[0].attribute(QNetworkRequest::RedirectPolicyAttribute).toInt(), int(QNetworkRequest::ManualRedirectPolicy));
        QVERIFY(!network->requests[0].hasRawHeader("Authorization"));
        QVERIFY(updater.canDownload()); QVERIFY(!updater.canInstall());
        network->responses.enqueue({installerBytes}); updater.downloadUpdate(); updater.downloadUpdate();
        QTRY_VERIFY2(updater.state() == "ready", qPrintable(updater.status()));
        QCOMPARE(network->requests.size(), 2);
        QFile file(updater.m_installerPath); QVERIFY(file.open(QIODevice::ReadOnly)); QCOMPARE(file.readAll(), installerBytes); file.close();
        QSignalSpy launch(&updater, &ReleaseUpdater::installerStarted);
        updater.installUpdate(false); QCOMPARE(launch.count(), 0); QCOMPARE(updater.state(), QString("ready"));
    }
    void missingDigestFetchesOfficialChecksums() {
        ReleaseUpdater updater; auto network = attach(updater);
        network->responses.enqueue({releaseJson("0.2.0", false)});
        network->responses.enqueue({QCryptographicHash::hash(installerBytes, QCryptographicHash::Sha256).toHex() + "  ShowPsiSi-0.2.0-windows-x64-setup.exe\n"});
        updater.checkForUpdates(); QTRY_COMPARE(updater.state(), QString("available"));
        QCOMPARE(network->requests.size(), 2); QVERIFY(network->requests[1].url().toString().endsWith("/v0.2.0/SHA256SUMS"));
        QCOMPARE(updater.m_release.sha256, QCryptographicHash::hash(installerBytes, QCryptographicHash::Sha256));
    }
    void malformedChecksumNeverEnablesDownload() {
        ReleaseUpdater updater; auto network = attach(updater);
        network->responses.enqueue({releaseJson("0.2.0", false)}); network->responses.enqueue({"bad checksum"});
        updater.checkForUpdates(); QTRY_COMPARE(updater.state(), QString("error")); QVERIFY(!updater.canDownload()); QVERIFY(!updater.canInstall());
    }
    void networkFailuresAndManualRetry_data() { QTest::addColumn<int>("status"); for (int code : {403, 429, 500}) QTest::newRow(qPrintable(QString::number(code))) << code; }
    void networkFailuresAndManualRetry() {
        QFETCH(int, status);
        ReleaseUpdater updater; auto network = attach(updater);
        network->responses.enqueue({{}, status}); updater.checkForUpdates(); QTRY_COMPARE(updater.state(), QString("error"));
        QVERIFY(!updater.busy()); QVERIFY(!updater.canInstall());
        network->responses.enqueue({releaseJson()}); updater.checkForUpdates(); QTRY_COMPARE(updater.state(), QString("available"));
    }
    void notPublishedIsNotUpToDate() {
        ReleaseUpdater updater; auto network = attach(updater);
        network->responses.enqueue({{}, 404}); updater.checkForUpdates(); QTRY_COMPARE(updater.state(), QString("no-release")); QVERIFY(!updater.canDownload());
    }
    void timeoutAndSslErrorFailClosed() {
        ReleaseUpdater updater; auto network = attach(updater);
        network->responses.enqueue({{}, 200, {}, true}); updater.checkForUpdates(); updater.m_deadline.start(1);
        QTRY_COMPARE(updater.state(), QString("error")); QVERIFY(!updater.busy());
        network->responses.enqueue({{}, 0, {}, false, QNetworkReply::SslHandshakeFailedError}); updater.checkForUpdates();
        QTRY_COMPARE(updater.state(), QString("error")); QVERIFY(!updater.canDownload());
    }
    void cancellationInvalidatesOldReplyAndPermitsRetry() {
        ReleaseUpdater updater; auto network = attach(updater);
        network->responses.enqueue({releaseJson(), 200, {}, true}); updater.checkForUpdates();
        auto old = network->last; updater.cancel(); QCOMPARE(updater.state(), QString("cancelled"));
        QVERIFY(old->aborted); old->publish(); QCOMPARE(updater.state(), QString("cancelled"));
        network->responses.enqueue({releaseJson()}); updater.checkForUpdates(); QTRY_COMPARE(updater.state(), QString("available"));
    }
    void cancelledPartialInstallerIsNeverPublished() {
        ReleaseUpdater updater; auto network = attach(updater);
        network->responses.enqueue({releaseJson()}); updater.checkForUpdates(); QTRY_COMPARE(updater.state(), QString("available"));
        network->responses.enqueue({installerBytes.left(10), 200, {}, true}); updater.downloadUpdate(); QVERIFY2(network->last && updater.state() == "downloading", qPrintable(updater.status())); network->last->publish(false);
        const QString path = updater.m_installerPath; QVERIFY(!QFileInfo::exists(path)); updater.cancel();
        QCOMPARE(updater.state(), QString("cancelled")); QVERIFY(!QFileInfo::exists(path)); QVERIFY(!updater.canInstall()); QVERIFY(updater.canDownload());
    }
    void hashMismatchAndTruncationAndOversizeRemoveDownload_data() {
        QTest::addColumn<QByteArray>("body");
        QTest::newRow("hash") << QByteArray(installerBytes.size(), 'x');
        QTest::newRow("short") << installerBytes.left(10);
        QTest::newRow("long") << installerBytes + "extra";
    }
    void hashMismatchAndTruncationAndOversizeRemoveDownload() {
        QFETCH(QByteArray, body);
        ReleaseUpdater updater; auto network = attach(updater);
        network->responses.enqueue({releaseJson()}); updater.checkForUpdates(); QTRY_COMPARE(updater.state(), QString("available"));
        network->responses.enqueue({body}); updater.downloadUpdate(); const QString path = updater.m_installerPath;
        QTRY_COMPARE(updater.state(), QString("error")); QVERIFY(!QFileInfo::exists(path)); QVERIFY(!updater.canInstall());
    }
    void tamperAndPendingOperationsBlockInstall() {
        ReleaseUpdater updater; auto network = attach(updater);
        network->responses.enqueue({releaseJson()}); updater.checkForUpdates(); QTRY_COMPARE(updater.state(), QString("available"));
        network->responses.enqueue({installerBytes}); updater.downloadUpdate(); QTRY_COMPARE(updater.state(), QString("ready"));
        QSignalSpy launch(&updater, &ReleaseUpdater::installerStarted);
        updater.setInstallGuard([] { return false; }); updater.installUpdate(true);
        QCOMPARE(updater.state(), QString("ready")); QCOMPARE(launch.count(), 0); QVERIFY(updater.status().contains("operations"));
        updater.setInstallGuard([] { return true; });
        QFile file(updater.m_installerPath); QVERIFY(file.open(QIODevice::WriteOnly | QIODevice::Truncate)); file.write("tampered"); file.close();
        updater.installUpdate(true); QCOMPARE(updater.state(), QString("error")); QCOMPARE(launch.count(), 0);
    }
    void rejectMetadataRedirectAndUnknownAssetRedirect() {
        ReleaseUpdater updater; auto network = attach(updater);
        network->responses.enqueue({{}, 302, QUrl("https://api.github.com/evil")}); updater.checkForUpdates(); QTRY_COMPARE(updater.state(), QString("error")); QCOMPARE(network->requests.size(), 1);
        network->responses.enqueue({releaseJson()}); updater.checkForUpdates(); QTRY_COMPARE(updater.state(), QString("available"));
        network->responses.enqueue({{}, 302, QUrl("https://evil.example/installer.exe")}); updater.downloadUpdate(); QTRY_COMPARE(updater.state(), QString("error")); QCOMPARE(network->requests.size(), 3);
    }
    void approvedAssetRedirectAndLoopBound() {
        ReleaseUpdater updater; auto network = attach(updater);
        network->responses.enqueue({releaseJson()}); updater.checkForUpdates(); QTRY_COMPARE(updater.state(), QString("available"));
        network->responses.enqueue({{}, 302, QUrl("https://release-assets.githubusercontent.com/fixture")}); network->responses.enqueue({installerBytes});
        updater.downloadUpdate(); QTRY_COMPARE(updater.state(), QString("ready")); QCOMPARE(network->requests.size(), 3);
        network->responses.enqueue({releaseJson()}); updater.checkForUpdates(); QTRY_COMPARE(updater.state(), QString("available"));
        for (int i = 0; i < 4; ++i) network->responses.enqueue({{}, 302, QUrl("https://release-assets.githubusercontent.com/loop")});
        updater.downloadUpdate(); QTRY_COMPARE(updater.state(), QString("error")); QCOMPARE(network->requests.size(), 8);
    }
    void excessiveMetadataIsRejected() {
        ReleaseUpdater updater; auto network = attach(updater); network->responses.enqueue({QByteArray(MaxMetadataBytes + 1, 'x')});
        updater.checkForUpdates(); QTRY_COMPARE(updater.state(), QString("error")); QVERIFY(!updater.canDownload());
    }
};
int main(int argc, char** argv) {
    QTemporaryDir isolatedHome;
    if (!isolatedHome.isValid()) return 2;
    qputenv("HOME", isolatedHome.path().toUtf8());
    qputenv("XDG_CACHE_HOME", (isolatedHome.path() + "/cache").toUtf8());
    QCoreApplication application(argc, argv);
    application.setOrganizationName("ShowPsiSiTests");
    application.setApplicationName("UpdaterContract");
    ReleaseUpdaterTests tests;
    return QTest::qExec(&tests, argc, argv);
}
#include "test_updates.moc"

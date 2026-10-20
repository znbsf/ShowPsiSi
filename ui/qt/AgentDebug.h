#pragma once
#include <QObject>
#include <QQuickWindow>
#include <QQuickItem>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QSaveFile>
#include <QFile>
#include <QDir>
#include <QTimer>
#include <QUuid>
#include <QDateTime>
#include <QStandardPaths>
#include <QCryptographicHash>
#include <QCoreApplication>
#include <QRegularExpression>
#include <QFileInfo>
#include <QGuiApplication>
#include <functional>

// Deliberate local diagnostic feature, not an engine test gate. No network,
// arbitrary code evaluation or stream/file mutation is exposed by this API.
class AgentDebug : public QObject {
    Q_OBJECT
    QQuickWindow* window = nullptr;
    QString session;
    QTimer poll;
    std::function<void(const QString&)> tracer;
    void trace(const QString& value) const { if (tracer) tracer(value); }
    static bool writeJson(const QString& path, const QJsonObject& value) {
        QSaveFile file(path);
        const auto bytes = QJsonDocument(value).toJson(QJsonDocument::Indented);
        return file.open(QIODevice::WriteOnly) && file.write(bytes) == bytes.size() && file.commit();
    }
    QJsonObject qml(const char* method, const QJsonObject* argument = nullptr) const {
        QVariant result;
        bool ok = argument
            ? QMetaObject::invokeMethod(window, method, Q_RETURN_ARG(QVariant, result), Q_ARG(QVariant, argument->toVariantMap()))
            : QMetaObject::invokeMethod(window, method, Q_RETURN_ARG(QVariant, result));
        if (!ok) return {{"error", "UI diagnostic method unavailable"}};
        QJsonParseError error;
        const auto doc = QJsonDocument::fromJson(result.toString().toUtf8(), &error);
        if (error.error != QJsonParseError::NoError || !doc.isObject()) return {{"error", "UI returned invalid diagnostic JSON"}};
        return doc.object();
    }
    void receive() {
        for (const auto& name : QDir(session).entryList({"*.request.json"}, QDir::Files, QDir::Name).mid(0, 8)) {
            const auto id = name.left(name.size() - 13);
            if (!QRegularExpression("^[a-f0-9]{32}$").match(id).hasMatch()) continue;
            QFile file(session + "/" + name);
            if (file.size() > 65536 || !file.open(QIODevice::ReadOnly)) continue;
            QJsonParseError error;
            const auto doc = QJsonDocument::fromJson(file.readAll(), &error);
            file.close();
            // Consume each request exactly once, even if its producer retries.
            if (!file.rename(session + "/" + id + ".consumed.json")) continue;
            const auto request = doc.object();
            QJsonObject result;
            const auto method = request.value("method").toString();
            trace("agent_consumed_" + id + "_" + method);
            if (error.error != QJsonParseError::NoError || !doc.isObject() || request.value("id") != id)
                result = {{"error", "Invalid request envelope"}};
            else if (method == "snapshot") result = snapshot();
            else if (method == "capture") result = capture(session + "/captures");
            else if (method == "action") {
                const auto params = request.value("params").toObject();
                result = qml("agentAction", &params);
            } else result = {{"error", "Unknown method; use snapshot, capture or action"}};
            trace("agent_write_begin_" + id);
            const bool written = writeJson(session + "/" + id + ".response.json", {{"id", id}, {"ok", !result.contains("error")}, {"result", result}});
            trace(QString(written ? "agent_write_ok_" : "agent_write_failed_") + id);
            if (!written) qWarning("Could not publish UI diagnostic response");
        }
    }
public:
    explicit AgentDebug(QObject* parent = nullptr) : QObject(parent) {}
    void setTrace(std::function<void(const QString&)> value) { tracer = std::move(value); }
    void attach(QQuickWindow* value) {
        window = value;
        const auto requested = qEnvironmentVariable("SHOWPSISI_AGENT_DIR");
        if (requested.isEmpty()) return;
        // A fresh directory is a session capability. Never attach to another
        // process's session or consume stale commands from an earlier launch.
        if (!QDir::isAbsolutePath(requested) || QFileInfo::exists(requested) || !QDir().mkdir(requested)) {
            qWarning("Agent session requires a new absolute directory"); return;
        }
        session = requested;
        if (!writeJson(session + "/session.json", {{"schema_version", 1}, {"frontend", "qt"},
            {"pid", double(QCoreApplication::applicationPid())}, {"methods", QJsonArray{"snapshot", "capture", "action"}},
            {"scope", "local UI inspection; no arbitrary eval, engine edits or exports"}})) {
            qWarning("Could not publish agent session"); session.clear(); return;
        }
        connect(&poll, &QTimer::timeout, this, &AgentDebug::receive);
        poll.start(80);
    }
    QJsonObject snapshot() const {
        trace("agent_state_begin");
        auto result = qml("agentState");
        trace("agent_state_end");
        result["schema_version"] = 1;
        result["frontend"] = "qt";
        result["captured_at"] = QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs);
        result["runtime"] = QJsonObject{{"qt", qVersion()}, {"platform", QGuiApplication::platformName()},
            {"pid", double(QCoreApplication::applicationPid())}, {"executable", QCoreApplication::applicationFilePath()}};
        result["viewport"] = QJsonObject{{"width", window->width()}, {"height", window->height()}, {"device_pixel_ratio", window->devicePixelRatio()}};
        QJsonArray controls;
        std::function<void(QQuickItem*)> visit = [&](QQuickItem* item) {
            if (controls.size() >= 1000) return;
            if (!item->objectName().isEmpty()) {
                const auto r = item->mapRectToScene(QRectF(0, 0, item->width(), item->height()));
                controls.append(QJsonObject{{"id", item->objectName()}, {"visible", item->isVisible()},
                    {"enabled", item->isEnabled()}, {"focused", item->hasActiveFocus()},
                    {"text", item->property("text").toString().left(512)},
                    {"color", item->property("color").toString()},
                    {"bounds", QJsonObject{{"x", r.x()}, {"y", r.y()}, {"width", r.width()}, {"height", r.height()}}}});
            }
            for (auto child : item->childItems()) visit(child);
        };
        trace("agent_controls_begin");
        visit(window->contentItem());
        trace("agent_controls_end");
        result["controls"] = controls;
        result["controls_limit"] = 1000;
        return result;
    }
    QJsonObject capture(const QString& base) {
        auto state = snapshot();
        if (state.contains("error")) return state;
        if (!state.value("settled").toBool()) return {{"error", "UI is busy; wait for settled=true before capture"}};
        const auto id = QUuid::createUuid().toString(QUuid::Id128);
        const auto directory = base + "/" + id;
        if (!QDir().mkpath(directory)) return {{"error", "Cannot create diagnostic directory"}};
        const auto pixels = window->grabWindow();
        if (pixels.isNull()) return {{"error", "Window capture returned no pixels"}, {"directory", directory}};
        QSaveFile image(directory + "/screenshot.png");
        if (!image.open(QIODevice::WriteOnly) || !pixels.save(&image, "PNG") || !image.commit())
            return {{"error", "Screenshot write failed"}, {"directory", directory}};
        if (!writeJson(directory + "/state.json", state)) return {{"error", "State write failed"}, {"directory", directory}};
        QFile png(directory + "/screenshot.png"); png.open(QIODevice::ReadOnly);
        const auto hash = QString(QCryptographicHash::hash(png.readAll(), QCryptographicHash::Sha256).toHex());
        QJsonObject manifest{{"schema_version", 1}, {"frontend", "qt"}, {"capture_id", id},
            {"screenshot", "screenshot.png"}, {"state", "state.json"}, {"screenshot_sha256", hash},
            {"width", pixels.width()}, {"height", pixels.height()}, {"complete", true}};
        // Manifest is the completion marker, published after checked PNG/JSON writes.
        if (!writeJson(directory + "/manifest.json", manifest)) return {{"error", "Manifest write failed"}};
        return {{"directory", directory}, {"manifest", manifest}};
    }
    Q_INVOKABLE QString saveBundle() {
        const auto base = session.isEmpty() ? QStandardPaths::writableLocation(QStandardPaths::PicturesLocation) + "/ShowPsiSi" : session + "/captures";
        const auto result = capture(base);
        return result.contains("error") ? "Diagnostics failed: " + result.value("error").toString() : "Diagnostics saved: " + result.value("directory").toString();
    }
};

#include <QGuiApplication>
#include <QQuickTextDocument>
#include <QSyntaxHighlighter>
#include <QRegularExpression>
#include <QSaveFile>
#include <QTextBlock>
#include <QTextLayout>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QQuickStyle>
#include <QProcess>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QFile>
#include <QDir>
#include <QElapsedTimer>
#include <QTimer>
#include <QDateTime>
#include <QMouseEvent>
#include <QKeyEvent>
#include <QKeySequence>
#include <QQuickItem>
#include <QFileInfo>
#include <QJsonParseError>
#include <QHash>
#include <QSettings>
#include <QStandardPaths>
#include <QProcessEnvironment>
#include <cmath>
#include <memory>
#include <functional>
#include "AgentDebug.h"
#ifdef Q_OS_WIN
#include <windows.h>
#endif

#include "XmlHighlighter.h"
#include <QIcon>
#include <QLibrary>

class Bridge:public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantMap state READ state NOTIFY stateChanged)
    Q_PROPERTY(QVariantMap detail READ detail NOTIFY detailChanged)
    Q_PROPERTY(QString root READ root CONSTANT)
    Q_PROPERTY(QString sample READ sample CONSTANT)
    Q_PROPERTY(bool busy READ busy NOTIFY busyChanged)
    Q_PROPERTY(bool cancelling READ cancelling NOTIFY cancellingChanged)
    Q_PROPERTY(bool available READ available NOTIFY availabilityChanged)
    Q_PROPERTY(QString availability READ availability NOTIFY availabilityChanged)
    Q_PROPERTY(QString error READ error NOTIFY errorChanged)
    Q_PROPERTY(bool inspecting READ inspecting NOTIFY inspectingChanged)
    Q_PROPERTY(bool comparing READ comparing NOTIFY comparingChanged)
    struct Request { QString method; quint64 generation; };
    QProcess process;
    QByteArray buffer,queuedWrites;
    QVariantMap m_state,m_detail;
    QString m_root,m_sample,m_error,stderrTail,m_availability="starting";
    bool m_busy=false,m_cancelling=false,m_inspecting=false,m_comparing=false;
    int sequence=0,activeAnalysis=0,latestInspect=0,latestQuery=0,latestPreview=0,latestComparison=0;
    quint64 generation=0;
    QHash<int,Request> methods;
    QJsonArray recentResponses;
    QElapsedTimer clock;
    bool dataFrame=false,completeFrame=false;
    QQuickWindow* window=nullptr;

    void clearIntentions(){
        latestInspect=latestQuery=latestPreview=latestComparison=0;
        m_detail.clear();m_inspecting=false;m_comparing=false;
        emit detailChanged();emit inspectingChanged();emit comparingChanged();
        emit workspaceInvalidated();
    }
    void receive(const QJsonObject& msg){
        if(m_availability=="disconnected")return;
        if(msg.contains("event")){
            // Events from old scans, other operations and malformed request IDs
            // must never replace the active workspace.
            if(msg["event"]!="progress"||!m_busy||m_cancelling||
               msg["request_id"]!=QJsonValue(activeAnalysis)||!msg["state"].isObject())return;
            m_state=msg["state"].toObject().toVariantMap();emit stateChanged();return;
        }
        if(!msg["id"].isDouble())return;
        const int id=msg["id"].toInt();
        if(msg["id"]!=QJsonValue(id)||!methods.contains(id))return;
        if(!msg["result"].isObject()&&!msg["error"].isObject())return;
        const auto request=methods.take(id);
        const QString method=request.method;
        recentResponses.append(QJsonObject{{"id",id},{"method",method},{"ok",!msg.contains("error")},
            {"error",msg["error"].toObject().value("message")},{"at",QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)}});
        if(recentResponses.size()>40)recentResponses.removeFirst();
        if(request.generation!=generation)return;
        if((method=="analyze"&&id!=activeAnalysis)||(method=="inspect"&&id!=latestInspect)||
           (method=="query"&&id!=latestQuery)||(method=="preview_rename"&&id!=latestPreview)||
           (method=="diff_snapshots"&&id!=latestComparison))return;
        if(method=="inspect"){m_inspecting=false;emit inspectingChanged();}
        if(method=="diff_snapshots"){m_comparing=false;emit comparingChanged();}
        const bool cancelRequested=method=="analyze"&&m_cancelling;
        // Only the original analyze terminal settles the scan. A cancellation
        // acknowledgement merely says that the worker saw the request.
        if(method=="analyze"){
            activeAnalysis=0;m_busy=false;m_cancelling=false;
            emit busyChanged();emit cancellingChanged();mark("scan_response");
        }
        if(msg.contains("error")){
            const auto error=msg["error"].toObject();
            const bool cancelled=method=="analyze"&&error["code"]=="analysis_cancelled";
            if(method=="analyze"){
                m_state=error["data"].toObject()["state"].toObject().toVariantMap();
                clearIntentions();emit stateChanged();
            }
            m_error=cancelled?QString():error["message"].toString();emit errorChanged();
            emit response(method,error.toVariantMap());
        }else{
            if(!m_error.isEmpty()){m_error.clear();emit errorChanged();}
            QVariantMap result=msg["result"].toObject().toVariantMap();
            if(method=="analyze"||method=="query"){m_state=result;emit stateChanged();}
            if(method=="inspect"){m_detail=result;emit detailChanged();}
            if(cancelRequested)result["cancel_requested"]=true;
            emit response(method,result);
        }
    }
public:
    Q_INVOKABLE QVariantMap diagnostics() const {
        return {{"pending",methods.size()},{"recent_responses",recentResponses.toVariantList()},
            {"backend",m_availability},{"error",m_error},{"stderr_tail",stderrTail}};
    }
    Bridge(){
        clock.start();
        // Runtime discovery never trusts the working directory. Packaged resources
        // live one level above bin; source builds may use an explicit absolute root.
        const QDir executableDirectory(QCoreApplication::applicationDirPath());
        const QString rootOverride=qEnvironmentVariable("SHOWPSISI_ROOT");
        if(!rootOverride.isEmpty()){
            if(!QDir::isAbsolutePath(rootOverride)){backendStopped("SHOWPSISI_ROOT must be an absolute directory.");return;}
            m_root=QDir::cleanPath(rootOverride);
        }else if(QFileInfo::exists(executableDirectory.filePath("showpsisi-portable.json"))){
            m_root=QDir::cleanPath(executableDirectory.absoluteFilePath(".."));
        }else{
            for(const auto& relative:{"..","../..","../../..","."}){
                const QString candidate=executableDirectory.absoluteFilePath(relative);
                if(QFileInfo::exists(candidate+"/api/tools.json")){m_root=QDir::cleanPath(candidate);break;}
            }
        }
        if(m_root.isEmpty()||!QFileInfo(m_root+"/api/tools.json").isFile()){
            backendStopped("Required application resource api/tools.json is missing. Extract the complete portable archive.");return;
        }
        m_sample=qEnvironmentVariable("SHOWPSISI_SAMPLE",m_root+"/samples/generated/lab.ts");
        if(!QDir::isAbsolutePath(m_sample)){backendStopped("SHOWPSISI_SAMPLE must be an absolute path.");return;}
        connect(&process,&QProcess::readyReadStandardOutput,this,[this]{
            buffer+=process.readAllStandardOutput();int nl;
            while((nl=buffer.indexOf('\n'))>=0){
                QJsonParseError parseError;auto doc=QJsonDocument::fromJson(buffer.left(nl),&parseError);buffer.remove(0,nl+1);
                if(parseError.error!=QJsonParseError::NoError||!doc.isObject()){m_error="Invalid backend response: "+parseError.errorString();emit errorChanged();continue;}
                receive(doc.object());
            }
        });
        connect(&process,&QProcess::started,this,[this]{
            m_availability="ready";emit availabilityChanged();mark("backend_started");
            if(!queuedWrites.isEmpty()){process.write(queuedWrites);queuedWrites.clear();}
        });
        connect(&process,&QProcess::readyReadStandardError,this,[this]{stderrTail=(stderrTail+QString::fromUtf8(process.readAllStandardError())).right(4096);});
        connect(&process,&QProcess::errorOccurred,this,[this]{backendStopped(process.errorString());});
        connect(&process,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this](int code,QProcess::ExitStatus status){
            backendStopped(QString("Backend stopped (%1, %2). %3").arg(code).arg(status==QProcess::CrashExit?"crash":"exit",stderrTail.trimmed()));
        });
        QString binary=executableDirectory.filePath("showpsisi-core");
#ifdef Q_OS_WIN
        binary+=".exe";
#endif
        if(QFileInfo::exists(executableDirectory.filePath("showpsisi-portable.json"))){
            for(const auto& name:{"tsduck.tables.model.xml","tsduck.dtv.names","tscore.time.xml","tscore.ip.names"}){
                if(!QFileInfo(executableDirectory.filePath(name)).isFile()){
                    backendStopped(QString("Required runtime model/name file missing: %1. Extract the complete portable archive.").arg(name));return;
                }
            }
        }
        // Trusted local test/development configuration, never stream metadata.
        // Arguments are passed directly to QProcess; no shell interpolation.
        QStringList arguments={"--root",m_root};
        if(qEnvironmentVariableIsSet("SHOWPSISI_CORE_ARGS_JSON")){
            QJsonParseError error;
            const auto document=QJsonDocument::fromJson(qgetenv("SHOWPSISI_CORE_ARGS_JSON"),&error);
            bool valid=error.error==QJsonParseError::NoError&&document.isArray()&&document.array().size()<=128;
            arguments.clear();
            for(const auto value:document.array()){
                if(!value.isString()||value.toString().contains(QChar(0))){valid=false;break;}
                arguments.append(value.toString());
            }
            if(!valid){backendStopped("Invalid SHOWPSISI_CORE_ARGS_JSON: expected an array of at most 128 strings without null characters.");return;}
        }
        binary=qEnvironmentVariable("SHOWPSISI_CORE",binary);
        if(!QDir::isAbsolutePath(binary)||!QFileInfo(binary).isFile()){
            backendStopped("Backend executable is missing or SHOWPSISI_CORE is not an absolute file path: "+binary);return;
        }
        process.start(binary,arguments);
        mark("native_setup");
    }
    ~Bridge(){process.closeWriteChannel();if(!process.waitForFinished(1000)){process.kill();process.waitForFinished(1000);}}
    QVariantMap state()const{return m_state;} QVariantMap detail()const{return m_detail;}
    void backendStopped(const QString& reason){
        if(m_availability=="disconnected")return;
        m_availability="disconnected";m_error="Backend disconnected. Restart the application. "+reason;
        ++generation;activeAnalysis=0;m_busy=false;m_cancelling=false;
        methods.clear();queuedWrites.clear();m_state.clear();clearIntentions();
        emit availabilityChanged();emit errorChanged();emit busyChanged();emit cancellingChanged();emit stateChanged();
    }
    bool inspecting()const{return m_inspecting;}
    bool comparing()const{return m_comparing;}
    bool cancelling()const{return m_cancelling;}
    bool available()const{return m_availability=="ready";}
    QString availability()const{return m_availability;}
    QString root()const{return m_root;} QString sample()const{return m_sample;}bool busy()const{return m_busy;}QString error()const{return m_error;}
    void attach(QQuickWindow*w){window=w;connect(w,&QQuickWindow::frameSwapped,this,[this]{
        if(!dataFrame&&m_state.value("observations").toULongLong()>0){dataFrame=true;mark("first_paint");}
        if(!completeFrame&&!m_busy&&!m_cancelling&&m_state.value("complete").toBool()){completeFrame=true;mark("complete_paint");emit completedPaint();}
    },Qt::QueuedConnection);}
    Q_INVOKABLE void cancelAnalysis(){
        if(!available()||!m_busy||m_cancelling||!activeAnalysis)return;
        m_cancelling=true;
        // Invalidate every outstanding evidence/edit intention, retaining only
        // the original scan whose terminal response must still be observed.
        const auto analyze=methods.value(activeAnalysis);methods.clear();methods.insert(activeAnalysis,analyze);
        clearIntentions();emit cancellingChanged();mark("cancel_requested");
        send("cancel_analysis",{{"request_id",activeAnalysis}});
    }
    Q_INVOKABLE void send(QString method,QVariantMap params={}){
        if(m_availability=="disconnected"||process.state()==QProcess::NotRunning){
            backendStopped("Backend is not running. Check SHOWPSISI_CORE.");return;
        }
        if(m_busy&&method!="cancel_analysis")return;
        if(method=="cancel_analysis"&&(!m_busy||!m_cancelling))return;
        if(!m_error.isEmpty()){m_error.clear();emit errorChanged();}
        int id=++sequence;
        if(method=="analyze"){
            ++generation;methods.clear();activeAnalysis=id;
            m_busy=true;m_cancelling=false;m_state.clear();clearIntentions();
            dataFrame=completeFrame=false;emit busyChanged();emit cancellingChanged();emit stateChanged();mark("analyze_requested");
        }
        if(method=="inspect"){latestInspect=id;m_detail.clear();m_inspecting=true;emit detailChanged();emit inspectingChanged();}
        if(method=="query"){latestQuery=id;latestInspect=latestPreview=0;m_detail.clear();m_inspecting=false;emit detailChanged();emit inspectingChanged();}
        if(method=="preview_rename")latestPreview=id;
        if(method=="diff_snapshots"){latestComparison=id;m_comparing=true;emit comparingChanged();}
        methods.insert(id,{method,generation});
        QJsonObject request{{"id",id},{"method",method},{"params",QJsonObject::fromVariantMap(params)}};
        QByteArray wire=QJsonDocument(request).toJson(QJsonDocument::Compact)+'\n';
        if(process.state()==QProcess::Starting)queuedWrites+=wire;else if(process.write(wire)<0)backendStopped(process.errorString());
    }
    Q_INVOKABLE void mark(QString event){QString path=qEnvironmentVariable("SHOWPSISI_TRACE");if(path.isEmpty())return;QFile file(path);if(file.open(QIODevice::Append)){QJsonObject value{{"event",event},{"ms",clock.nsecsElapsed()/1e6},{"wall_ms",double(QDateTime::currentMSecsSinceEpoch())},{"backend_pid",double(process.processId())}};file.write(QJsonDocument(value).toJson(QJsonDocument::Compact)+'\n');}}
    Q_INVOKABLE QString env(QString name){return qEnvironmentVariable(name.toUtf8().constData());}
    Q_INVOKABLE QString localPath(QUrl url){return url.toLocalFile();}
    Q_INVOKABLE QUrl fileUrl(QString path){return QUrl::fromLocalFile(path);}
    Q_INVOKABLE QUrl parentFolder(QString path){return QUrl::fromLocalFile(QFileInfo(path).absolutePath());}
    Q_INVOKABLE QUrl exportFolder(){
        // Resource/install directories are not user output locations. In a
        // portable or read-only installation the home folder is still useful.
        for(const auto& path:{QStandardPaths::writableLocation(QStandardPaths::DocumentsLocation),QDir::homePath()}){
            const QFileInfo directory(path);
            if(directory.isDir()&&directory.isWritable())return QUrl::fromLocalFile(directory.absoluteFilePath());
        }
        return QUrl::fromLocalFile(QDir::homePath()); // The picker can choose another writable folder.
    }
    Q_INVOKABLE QUrl suggestedExport(QUrl folder,QString source,QString format){
        QString stem;
        for(const auto character:QFileInfo(source).completeBaseName()){
            // Captured source names may contain controls, separators or markup.
            // Keep a short portable leaf name; never derive directories from it.
            stem+=character.isLetterOrNumber()||character=='-'||character=='_'?character:QChar('-');
            if(stem.size()>=80)break;
        }
        if(stem.isEmpty())stem="capture";
        return QUrl::fromLocalFile(QDir(folder.toLocalFile()).filePath(stem+"-edited-si."+(format=="bin"?"bin":"ts")));
    }
    Q_INVOKABLE QVariantMap exportDestination(QUrl url,QString format){
        if(!url.isLocalFile()||url.toLocalFile().isEmpty())return {{"error","Choose a local output file."}};
        if(format!="ts"&&format!="bin")return {{"error","Choose TS or BIN format."}};
        QString path=url.toLocalFile();
        if(path.contains(QChar(0)))return {{"error","The output path contains a null character."}};
        const QFileInfo file(path);
        if(file.fileName().isEmpty()||file.isDir())return {{"error","Choose a new file name, not a folder."}};
        if(file.suffix().isEmpty())path+="."+format;
        else if(file.suffix().compare(format,Qt::CaseInsensitive)!=0)
            return {{"error",QString("Use a .%1 file name for the selected %2 format.").arg(format,format.toUpper())}};
        // No existence precheck can prevent a race. The engine exclusively
        // creates both output and manifest and reports any competing writer.
        return {{"path",QFileInfo(path).absoluteFilePath()}};
    }
    Q_INVOKABLE QString json(QVariant value){return QString::fromUtf8(QJsonDocument::fromVariant(value).toJson(QJsonDocument::Indented));}
    std::unique_ptr<QSettings> layoutSettings()const{
        const QString path=qEnvironmentVariable("SHOWPSISI_SETTINGS_PATH");
        return path.isEmpty()?std::make_unique<QSettings>():std::make_unique<QSettings>(path,QSettings::IniFormat);
    }
    static bool validLayout(const QVariantMap& layout){
        if(layout.value("version").toInt()!=1)return false;
        const QList<QPair<QString,QPair<double,double>>> bounds={{"explorer",{150,480}},{"inspector",{330,1600}},{"timeline",{105,350}}};
        for(const auto& item:bounds){bool ok=false;const double value=layout.value(item.first).toDouble(&ok);if(!ok||!std::isfinite(value)||value<item.second.first||value>item.second.second)return false;}
        return true;
    }
    // Keep native move/resize/snap/accessibility. Windows DWM supports dark
    // decorations (20), caption (35) and text (36); unsupported attributes are
    // simply ignored. Linux/macOS window managers continue owning decorations.
    Q_INVOKABLE void themeChrome(bool light, QColor caption, QColor text){
#ifdef Q_OS_WIN
        if(!window)return;
        using SetAttribute=HRESULT(WINAPI*)(HWND,DWORD,LPCVOID,DWORD);
        auto setAttribute=reinterpret_cast<SetAttribute>(QLibrary::resolve("dwmapi", "DwmSetWindowAttribute"));
        if(!setAttribute)return;
        const HWND handle=reinterpret_cast<HWND>(window->winId());
        const BOOL dark=!light;setAttribute(handle,20,&dark,sizeof(dark));
        const COLORREF background=RGB(caption.red(),caption.green(),caption.blue());
        const COLORREF foreground=RGB(text.red(),text.green(),text.blue());
        setAttribute(handle,35,&background,sizeof(background));setAttribute(handle,36,&foreground,sizeof(foreground));
#else
        Q_UNUSED(light); Q_UNUSED(caption); Q_UNUSED(text);
#endif
    }
    Q_INVOKABLE QString loadTheme(){return layoutSettings()->value("workbenchTheme","dark").toString();}
    Q_INVOKABLE void saveTheme(QString theme){auto settings=layoutSettings(); settings->setValue("workbenchTheme",theme=="light"?"light":"dark");settings->sync();}
    Q_INVOKABLE QVariantMap loadLayout(){
        auto settings=layoutSettings();
        const auto layout=QJsonDocument::fromJson(settings->value("workbenchLayout").toByteArray()).object().toVariantMap();
        return validLayout(layout)?layout:QVariantMap{{"version",1},{"explorer",180},{"inspector",520},{"timeline",105}};
    }
    Q_INVOKABLE bool saveLayout(QVariantMap layout){
        if(!validLayout(layout))return false;
        auto settings=layoutSettings();settings->setValue("workbenchLayout",QJsonDocument::fromVariant(layout).toJson(QJsonDocument::Compact));settings->sync();return settings->status()==QSettings::NoError;
    }
    Q_INVOKABLE bool resetLayout(){auto settings=layoutSettings();settings->remove("workbenchLayout");settings->sync();return settings->status()==QSettings::NoError;}
    Q_INVOKABLE bool xmlHighlightActive(QObject* object){
        auto document=qobject_cast<QQuickTextDocument*>(object);
        if(!document || !document->property("xmlHighlighted").toBool())return false;
        for(auto block=document->textDocument()->begin();block.isValid();block=block.next())
            if(block.layout() && block.layout()->formats().size()>=3)return true;
        return false;
    }
    Q_INVOKABLE void highlightXml(QObject* object, bool light=false){
        if(auto document=qobject_cast<QQuickTextDocument*>(object)) {
            auto highlighter=dynamic_cast<XmlHighlighter*>(document->textDocument()->findChild<QObject*>("xmlSyntax"));
            if(!highlighter) {highlighter=new XmlHighlighter(document->textDocument());highlighter->setObjectName("xmlSyntax");document->setProperty("xmlHighlighted",true);}
            highlighter->setLight(light);
        }
    }
    Q_INVOKABLE void capture(QString path){
        if(!window)return;
        QDir().mkpath(QFileInfo(path).absolutePath());
        QSaveFile file(path);
        const auto image=window->grabWindow();
        const bool ok=file.open(QIODevice::WriteOnly) && image.save(&file,"PNG") && file.commit();
        mark(ok?"screenshot_saved":"screenshot_failed");
    }
    Q_INVOKABLE bool click(QString name){if(!window)return false;std::function<QQuickItem*(QQuickItem*)> find=[&](QQuickItem* p)->QQuickItem*{if(p->objectName()==name)return p;for(auto c:p->childItems())if(auto found=find(c))return found;return nullptr;};auto item=find(window->contentItem());if(!item||!item->isVisible()||!item->isEnabled())return false;QPointF pos=item->mapToScene(QPointF(item->width()/2,item->height()/2));QMouseEvent press(QEvent::MouseButtonPress,pos,pos,window->mapToGlobal(pos.toPoint()),Qt::LeftButton,Qt::LeftButton,Qt::NoModifier);QCoreApplication::sendEvent(window,&press);QMouseEvent release(QEvent::MouseButtonRelease,pos,pos,window->mapToGlobal(pos.toPoint()),Qt::LeftButton,Qt::NoButton,Qt::NoModifier);QCoreApplication::sendEvent(window,&release);return true;}
    Q_INVOKABLE bool hover(QString name){
        if(!window)return false;
        std::function<QQuickItem*(QQuickItem*)> find=[&](QQuickItem* item)->QQuickItem*{if(item->objectName()==name)return item;for(auto child:item->childItems())if(auto found=find(child))return found;return nullptr;};
        auto item=find(window->contentItem());if(!item||!item->isVisible())return false;
        const QPointF pos=item->mapToScene(QPointF(item->width()/2,item->height()/2));
        QMouseEvent move(QEvent::MouseMove,pos,pos,window->mapToGlobal(pos.toPoint()),Qt::NoButton,Qt::NoButton,Qt::NoModifier);
        QCoreApplication::sendEvent(window,&move);return true;
    }
    Q_INVOKABLE bool isExposed(QString name){
        if(!window)return false;
        std::function<QQuickItem*(QQuickItem*)> find=[&](QQuickItem* item)->QQuickItem*{if(item->objectName()==name&&item->isVisible())return item;for(auto child:item->childItems())if(auto found=find(child))return found;return nullptr;};
        auto item=find(window->contentItem());if(!item||item->width()<=0||item->height()<=0)return false;
        const QRectF bounds=item->mapRectToScene(QRectF(0,0,item->width(),item->height()));
        QRectF visible(0,0,window->width(),window->height());
        for(auto parent=item->parentItem();parent;parent=parent->parentItem())if(parent->clip())visible=visible.intersected(parent->mapRectToScene(QRectF(0,0,parent->width(),parent->height())));
        return visible.adjusted(-0.5,-0.5,0.5,0.5).contains(bounds);
    }
    Q_INVOKABLE bool drag(QString name,double dx,double dy){
        if(!window)return false;
        std::function<QQuickItem*(QQuickItem*)> find=[&](QQuickItem* item)->QQuickItem*{if(item->objectName()==name&&item->isVisible())return item;for(auto child:item->childItems())if(auto found=find(child))return found;return nullptr;};
        auto item=find(window->contentItem());if(!item||!item->isEnabled())return false;
        const QPointF start=item->mapToScene(QPointF(item->width()/2,item->height()/2)),end=start+QPointF(dx,dy);
        auto send=[&](QEvent::Type type,QPointF point,Qt::MouseButton button,Qt::MouseButtons buttons){QMouseEvent event(type,point,window->mapToGlobal(point.toPoint()),button,buttons,Qt::NoModifier);QCoreApplication::sendEvent(window,&event);};
        send(QEvent::MouseMove,start,Qt::NoButton,Qt::NoButton);send(QEvent::MouseButtonPress,start,Qt::LeftButton,Qt::LeftButton);
        send(QEvent::MouseMove,end,Qt::NoButton,Qt::LeftButton);send(QEvent::MouseButtonRelease,end,Qt::LeftButton,Qt::NoButton);return true;
    }
    Q_INVOKABLE QVariantMap textSafetyReport(QString marker){
        int matched=0,unsafe=0,tooltips=0;
        std::function<void(QQuickItem*)> visit=[&](QQuickItem* item){
            const auto format=item->property("textFormat");
            if(format.isValid()&&item->property("text").toString().contains(marker)){++matched;if(item->objectName()=="plainTooltipContent"&&item->isVisible())++tooltips;if(format.toInt()!=0)++unsafe;}
            for(auto child:item->childItems())visit(child);
        };
        if(window)visit(window->contentItem());
        return {{"matched_text_items",matched},{"unsafe_text_items",unsafe},{"tooltip_text_items",tooltips}};
    }
    Q_INVOKABLE bool key(QString sequenceText){
        if(!window)return false;
        const QKeySequence sequence(sequenceText);
        if(sequence.isEmpty())return false;
        const auto combination=sequence[0];
        QKeyEvent press(QEvent::KeyPress,combination.key(),combination.keyboardModifiers());
        QCoreApplication::sendEvent(window,&press);
        QKeyEvent release(QEvent::KeyRelease,combination.key(),combination.keyboardModifiers());
        QCoreApplication::sendEvent(window,&release);
        return true;
    }
    Q_INVOKABLE void testResult(QString text){QSaveFile f(qEnvironmentVariable("SHOWPSISI_TEST_RESULT"));const auto bytes=text.toUtf8();if(f.open(QIODevice::WriteOnly)&&f.write(bytes)==bytes.size()&&f.commit())mark("ui_test_done");else mark("ui_test_result_failed");}
signals:
    void stateChanged();void detailChanged();void busyChanged();void cancellingChanged();void availabilityChanged();void workspaceInvalidated();void inspectingChanged();void comparingChanged();void errorChanged();void response(QString method,QVariantMap result);void completedPaint();
};
int main(int argc,char**argv){
    // Discover the marker before QGuiApplication loads any platform plugins.
    // Windows uses the OS executable path, never argv[0] or the working directory.
#ifdef Q_OS_WIN
    wchar_t executablePath[32768];
    const DWORD pathLength=GetModuleFileNameW(nullptr,executablePath,32768);
    const QString executable=pathLength>0&&pathLength<32768?QString::fromWCharArray(executablePath,int(pathLength)):QString();
#else
    const QString executable=QFileInfo("/proc/self/exe").symLinkTarget();
#endif
    const bool packaged=!executable.isEmpty()&&QFileInfo::exists(QFileInfo(executable).absolutePath()+"/showpsisi-portable.json");
    bool development=false;
    for(int i=1;i<argc;++i)if(QString::fromLocal8Bit(argv[i])=="--showpsisi-development")development=true;
    if(packaged&&!development){
        for(const auto& name:QProcessEnvironment::systemEnvironment().keys()){
            const QString upper=name.toUpper();
            // Preserve display/accessibility preferences such as QT_SCALE_FACTOR.
            // Only resource/plugin selectors and application test hooks are reset.
            const QStringList discovery={"QT_PLUGIN_PATH","QT_QPA_PLATFORM_PLUGIN_PATH","QT_QPA_PLATFORM",
                "QML_IMPORT_PATH","QML2_IMPORT_PATH","TSDUCK","TSDUCK_ROOT","TSCORE_ROOT","TSPLUGINS_PATH","TSLIBPATH"};
            if(upper.startsWith("SHOWPSISI_")||discovery.contains(upper))
                qunsetenv(name.toUtf8().constData());
        }
    }
    QGuiApplication app(argc,argv);
    QIcon applicationIcon;
    for(int size : {16,24,32,48,64,128,256}) applicationIcon.addFile(QString(":/icons/showpsisi-%1.png").arg(size), QSize(size,size));
    QGuiApplication::setWindowIcon(applicationIcon);
    QGuiApplication::setDesktopFileName("org.showpsisi.ShowPsiSi");
    app.setOrganizationName("ShowPsiSi");app.setApplicationName("ShowPsiSi");QQuickStyle::setStyle("Basic");
    Bridge bridge;AgentDebug uiAgent;QQmlApplicationEngine engine;engine.rootContext()->setContextProperty("core",&bridge);
    engine.rootContext()->setContextProperty("uiAgent",&uiAgent);
    engine.loadFromModule("ShowPsiSi","Main");if(engine.rootObjects().isEmpty())return 1;
    auto window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());
    bridge.attach(window);uiAgent.attach(window);return app.exec();
}
#include "main.moc"

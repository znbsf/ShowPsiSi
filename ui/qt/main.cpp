#include <ctime>
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
#include <QThread>
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
#include <QSet>
#include <QSettings>
#include <QStringList>
#include <QStandardPaths>
#include <QProcessEnvironment>
#include <cmath>
#include <memory>
#include <functional>
#include "AgentDebug.h"
#include "ReleaseUpdater.h"
#ifdef Q_OS_WIN
#include <windows.h>
#endif

#include "XmlHighlighter.h"
#include <QIcon>
#include <QLibrary>

// The child process and every JSON decode/variant conversion live on this thread.
// At most one progress delivery is queued to the GUI. Reliable replies never
// share that lossy mailbox, including control ACKs and the original terminal.
class BackendTransport : public QObject {
    Q_OBJECT
    QProcess* process=nullptr;
    QTimer* progressTimer=nullptr;
    QByteArray buffer, pendingWrites;
    QJsonObject pendingProgress;
    bool progressInFlight=false, drainScheduled=false;
    void deliver(const QJsonObject& message) {
        emit frame(message, message.value("state").toObject().toVariantMap(),
                   message.value("result").toObject().toVariantMap(),
                   message.value("error").toObject().toVariantMap(),
                   QString::fromUtf8(QJsonDocument(message.value("result").toObject()).toJson(QJsonDocument::Compact)));
    }
    void drain() {
        drainScheduled=false;
        // Yield the worker event loop so pause/cancel writes cannot starve behind
        // a flood of lines. Parsing never occupies the GUI event loop.
        for(int count=0;count<32;++count){
            const auto nl=buffer.indexOf('\n'); if(nl<0)return;
            QJsonParseError error;
            const auto doc=QJsonDocument::fromJson(buffer.left(nl),&error);
            buffer.remove(0,nl+1);
            if(error.error!=QJsonParseError::NoError||!doc.isObject()) {
                emit protocolError("Invalid backend response: "+error.errorString());continue;
            }
            const auto message=doc.object();
            if(message.value("event")=="progress") {
                if(activeRequest.isUndefined() || message.value("request_id")!=activeRequest)continue;
                // Paused/resumed status transitions are control evidence, not
                // disposable telemetry. Deliver them reliably and in order.
                const auto status=message.value("state").toObject().value("analysis_status").toString();
                if(status=="paused"||lastStatus=="paused") {pendingProgress={};deliver(message);}
                else pendingProgress=message;
                lastStatus=status;
            } else { deliver(message); }
        }
        if(buffer.contains('\n')&&!drainScheduled){drainScheduled=true;QTimer::singleShot(0,this,[this]{drain();});}
    }
    QString lastStatus;
    QJsonValue activeRequest;
public slots:
    void start(QString binary,QStringList arguments) {
        process=new QProcess(this);progressTimer=new QTimer(this);progressTimer->setInterval(50);
        connect(progressTimer,&QTimer::timeout,this,[this]{
            if(progressInFlight||pendingProgress.isEmpty())return;
            progressInFlight=true;auto message=pendingProgress;pendingProgress={};deliver(message);
        });progressTimer->start();
        connect(process,&QProcess::readyReadStandardOutput,this,[this]{buffer+=process->readAllStandardOutput();if(!drainScheduled)drain();});
        connect(process,&QProcess::readyReadStandardError,this,[this]{emit stderrRead(QString::fromUtf8(process->readAllStandardError()).right(4096));});
        connect(process,&QProcess::started,this,[this]{emit started(process->processId());if(!pendingWrites.isEmpty()){process->write(pendingWrites);pendingWrites.clear();}});
        connect(process,&QProcess::errorOccurred,this,[this]{emit stopped(process->errorString());});
        connect(process,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this](int code,QProcess::ExitStatus status){
            // Preserve complete replies that arrived immediately before EOF.
            buffer+=process->readAllStandardOutput();while(buffer.contains('\n'))drain();
            emit stopped(QString("Backend stopped (%1, %2)").arg(code).arg(status==QProcess::CrashExit?"crash":"exit"));
        });
        process->start(binary,arguments);
    }
    void write(QByteArray wire){
        const auto request=QJsonDocument::fromJson(wire).object();
        if(request.value("method")=="analyze"){activeRequest=request.value("id");pendingProgress={};lastStatus.clear();}
        if(!process||process->state()==QProcess::Starting)pendingWrites+=wire;else if(process->state()==QProcess::Running)process->write(wire);}
    void acknowledgeProgress(){progressInFlight=false;}
    void shutdown(bool drainExports){
        if(!process)return;progressTimer->stop();process->closeWriteChannel();
        if(drainExports){process->waitForFinished(-1);return;}
        if(!process->waitForFinished(1000)){process->kill();process->waitForFinished(1000);}
    }
signals:
    void frame(QJsonObject message,QVariantMap state,QVariantMap result,QVariantMap error,QString resultJson);
    void protocolError(QString message);void stderrRead(QString text);void started(qint64 pid);void stopped(QString reason);
};

class Bridge:public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantMap state READ state NOTIFY stateChanged)
    Q_PROPERTY(QString stateJson READ stateJson NOTIFY stateChanged)
    Q_PROPERTY(QString detailJson READ detailJson NOTIFY detailChanged)
    Q_PROPERTY(QVariantMap detail READ detail NOTIFY detailChanged)
    Q_PROPERTY(QString root READ root CONSTANT)
    Q_PROPERTY(QString sample READ sample CONSTANT)
    Q_PROPERTY(bool busy READ busy NOTIFY busyChanged)
    Q_PROPERTY(QVariantMap progress READ progress NOTIFY progressChanged)
    Q_PROPERTY(bool paused READ paused NOTIFY pauseChanged)
    Q_PROPERTY(bool pausePending READ pausePending NOTIFY pauseChanged)
    Q_PROPERTY(bool loadingResults READ loadingResults NOTIFY busyChanged)
    Q_PROPERTY(QVariantMap remainingPages READ remainingPages NOTIFY stateChanged)
    Q_PROPERTY(bool exportPending READ exportPending NOTIFY exportPendingChanged)
    Q_PROPERTY(bool cancelling READ cancelling NOTIFY cancellingChanged)
    Q_PROPERTY(bool available READ available NOTIFY availabilityChanged)
    Q_PROPERTY(QString availability READ availability NOTIFY availabilityChanged)
    Q_PROPERTY(QString error READ error NOTIFY errorChanged)
    Q_PROPERTY(bool inspecting READ inspecting NOTIFY inspectingChanged)
    Q_PROPERTY(bool comparing READ comparing NOTIFY comparingChanged)
    struct Request { QString method; quint64 generation; QVariantMap params; };
    QThread transportThread;
    BackendTransport* transport=nullptr;
    qint64 backendPid=0;
    QVariantMap m_progress;
    bool m_paused=false,m_pausePending=false,m_pauseTarget=false,m_loadingResults=false;
    QString hydrationMethod;
    QStringList hydrationQueue;
    QVariantMap hydrationState;
    QHash<QString,QVariantList> hydrationCollections;
    QHash<QString,int> pageOffsets;
    QSet<QString> loadingPages;
    int hydrationEpoch=0;
    int awaitingPresentationEpoch=-1;
    QVariantMap m_state,m_detail;
    QString m_detailJson="{}";
    QString m_root,m_sample,m_error,stderrTail,m_availability="starting";
    bool m_busy=false,m_cancelling=false,m_inspecting=false,m_comparing=false;
    int sequence=0,activeAnalysis=0,latestInspect=0,latestQuery=0,latestPreview=0,latestComparison=0,latestTopology=0,latestDvbiImport=0,latestDvbiQuery=0,latestDvbiInspect=0;
    quint64 generation=0;
    QHash<int,Request> methods;
    QSet<int> pendingExports;
    QJsonArray recentResponses;
    QElapsedTimer clock,hydrationProgressClock;
    QThread traceThread;
    QObject* traceWriter=nullptr;
    QString tracePath;
    bool dataFrame=false,completeFrame=false;
    QQuickWindow* window=nullptr;
    static bool documentMethod(const QString& method){return method=="import_dvbi"||method=="query_dvbi"||method=="inspect_dvbi";}
    void clearTsRequests(){for(auto i=methods.begin();i!=methods.end();)if(!documentMethod(i->method))i=methods.erase(i);else ++i;}
    void clearIntentions(){
        latestInspect=latestQuery=latestPreview=latestComparison=latestTopology=0;
        const bool hadDetail=!m_detail.isEmpty(),wasInspecting=m_inspecting,wasComparing=m_comparing;
        m_detail.clear();m_detailJson="{}";m_inspecting=false;m_comparing=false;
        if(hadDetail)emit detailChanged();if(wasInspecting)emit inspectingChanged();if(wasComparing)emit comparingChanged();
        emit workspaceInvalidated();
    }
    void receive(const QJsonObject& msg,const QVariantMap& stateValue,const QVariantMap& resultValue,const QVariantMap& errorValue,const QString& resultJson){
        if(m_availability=="disconnected")return;
        if(msg.contains("event")){
            // Events from old scans, other operations and malformed request IDs
            // must never replace the active workspace.
            if(msg["event"]!="progress"||!m_busy||m_cancelling||
               msg["request_id"]!=QJsonValue(activeAnalysis)||!msg["state"].isObject())return;
            if(m_progress.isEmpty())clearIntentions();
            m_progress=stateValue;emit progressChanged();
            const bool paused=stateValue.value("analysis_status")=="paused";
            if(paused!=m_paused || (m_pausePending && paused==m_pauseTarget)){m_paused=paused;m_pausePending=false;emit pauseChanged();}
            return;
        }
        if(!msg["id"].isDouble())return;
        const int id=msg["id"].toInt();
        if(msg["id"]!=QJsonValue(id))return;
        if(!msg["result"].isObject()&&!msg["error"].isObject())return;
        // Export lifetime is independent of view/query generations. Never let a
        // navigation clear release the close/update guard before its terminal.
        if(pendingExports.remove(id))emit exportPendingChanged();
        if(!methods.contains(id))return;
        const auto request=methods.take(id);
        const QString method=request.method;
        recentResponses.append(QJsonObject{{"id",id},{"method",method},{"ok",!msg.contains("error")},
            {"error",msg["error"].toObject().value("message")},{"at",QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)}});
        if(recentResponses.size()>40)recentResponses.removeFirst();
        if(request.generation!=generation&&!documentMethod(method))return;
        if((method=="analyze"&&id!=activeAnalysis)||(method=="inspect"&&id!=latestInspect)||
           (method=="query"&&id!=latestQuery)||(method=="preview_rename"&&id!=latestPreview)||
           (method=="diff_snapshots"&&id!=latestComparison)||(method=="query_topology"&&id!=latestTopology)||
           (method=="import_dvbi"&&id!=latestDvbiImport)||(method=="query_dvbi"&&id!=latestDvbiQuery)||
           (method=="inspect_dvbi"&&id!=latestDvbiInspect))return;
        if(method=="inspect"){m_inspecting=false;emit inspectingChanged();}
        if(method=="diff_snapshots"){m_comparing=false;emit comparingChanged();}
        if(method=="query_result") {
            const QString collection=request.params.value("collection").toString();
            loadingPages.remove(collection);
            if(request.params.value("_epoch").toInt()!=hydrationEpoch)return;
            if(msg.contains("error")){
                const QString failedMethod=hydrationMethod.isEmpty()?"query_result":hydrationMethod;
                ++hydrationEpoch;hydrationQueue.clear();loadingPages.clear();pageOffsets.clear();hydrationCollections.clear();hydrationState.clear();hydrationMethod.clear();
                m_error=errorValue.value("message").toString();emit errorChanged();
                m_loadingResults=false;m_busy=false;m_state.clear();clearIntentions();emit resultLoading();emit stateChanged();emit busyChanged();
                emit response(failedMethod,errorValue);return;
            }
            const auto result=msg.value("result").toObject();
            const auto offset=request.params.value("offset").toLongLong();
            const auto items=result.value("items");const auto total=result.value("total");const auto next=result.value("next_offset");
            const auto expectedCutoff=request.params.contains("at_packet")?QJsonValue::fromVariant(request.params.value("at_packet")):QJsonValue(QJsonValue::Null);
            const double totalNumber=total.toDouble(-1),nextNumber=next.toDouble(-1);
            const qint64 end=offset+(items.isArray()?items.toArray().size():0);
            const bool valid=result.value("analysis_revision")==QJsonValue::fromVariant(hydrationState.value("analysis_revision")) &&
                result.value("collection").toString()==collection && result.value("at_packet")==expectedCutoff &&
                items.isArray() && items.toArray().size()<=request.params.value("limit").toInt() && resultJson.size()<=300000 &&
                total.isDouble() && std::isfinite(totalNumber) && totalNumber>=end && std::floor(totalNumber)==totalNumber &&
                (offset==0 || totalNumber==hydrationState.value("result_counts").toMap().value(collection,-1).toDouble()) &&
                ((next.isNull() && end==totalNumber) || (next.isDouble() && nextNumber==end && nextNumber>offset && nextNumber<totalNumber));
            if(!valid){
                const QString method=hydrationMethod.isEmpty()?"query_result":hydrationMethod;
                ++hydrationEpoch;hydrationQueue.clear();loadingPages.clear();pageOffsets.clear();hydrationCollections.clear();hydrationState.clear();hydrationMethod.clear();
                m_loadingResults=false;m_busy=false;m_state.clear();clearIntentions();m_error="Invalid result page: revision, collection, cutoff, count or cursor mismatch.";
                emit resultLoading();emit stateChanged();emit busyChanged();emit errorChanged();emit response(method,{{"code","invalid_result_page"},{"message",m_error}});return;
            }
            mark("page_rows_"+QString::number(items.toArray().size()));
            mark("page_begin_"+collection);emit resultPage(collection,resultJson);mark("page_js_"+collection);
            hydrationCollections[collection].append(resultValue.value("items").toList());
            auto counts=hydrationState.value("result_counts").toMap();counts[collection]=resultValue.value("total");hydrationState["result_counts"]=counts;
            if(resultValue.value("next_offset").isNull())pageOffsets.remove(collection);else pageOffsets[collection]=resultValue.value("next_offset").toInt();
            if(m_loadingResults){
                m_progress["loaded_items"]=m_progress.value("loaded_items").toInt()+resultValue.value("items").toList().size();
                if(hydrationProgressClock.elapsed()>=50){hydrationProgressClock.restart();emit progressChanged();mark("hydration_progress_emitted");}
                const int epoch=hydrationEpoch;
                if(pageOffsets.contains(collection))QTimer::singleShot(0,this,[this,collection,epoch]{if(epoch==hydrationEpoch)loadResultPage(collection,pageOffsets.value(collection));});
                else QTimer::singleShot(0,this,[this,epoch]{if(epoch==hydrationEpoch)loadHydrationPage();});
            }else{hydrationState[collection]=hydrationCollections.value(collection);m_state=hydrationState;emit stateChanged();}
            return;
        }
        if(method=="pause_analysis"||method=="resume_analysis"){
            if(msg.contains("error")||!resultValue.value("requested").toBool()){m_pausePending=false;emit pauseChanged();}
        }
        const bool cancelRequested=method=="analyze"&&m_cancelling;
        // Only the original analyze terminal settles the scan. A cancellation
        // acknowledgement merely says that the worker saw the request.
        if(method=="analyze"){
            const bool compactSuccess=!msg.contains("error")&&resultValue.contains("result_counts");
            activeAnalysis=0;m_cancelling=false;m_paused=false;m_pausePending=false;emit pauseChanged();
            // A successful compact scan immediately enters hydration. Never expose
            // an idle interval which enables conflicting source/inspection controls.
            if(!compactSuccess){m_busy=false;emit busyChanged();}
            else mark(m_busy ? "compact_terminal_busy" : "compact_terminal_idle_error");
            emit cancellingChanged();mark("scan_response");
        }
        if(msg.contains("error")){
            const auto error=msg["error"].toObject();
            const bool cancelled=method=="analyze"&&error["code"]=="analysis_cancelled";
            if(method=="analyze"&&!errorValue.value("data").toMap().value("state_preserved").toBool()){
                m_state=errorValue.value("data").toMap().value("state").toMap();
                clearIntentions();emit stateChanged();
            }
            m_error=cancelled?QString():error["message"].toString();emit errorChanged();
            auto reportedError=errorValue;if(method=="query_packet"||method=="query_service"||method=="query_carousel"||method=="query_teletext")reportedError["request"]=request.params;
            emit response(method,reportedError);
        }else{
            if(!m_error.isEmpty()){m_error.clear();emit errorChanged();}
            QVariantMap result=resultValue;
            if(cancelRequested)result["cancel_requested"]=true;
            if(method=="analyze"&&m_progress.isEmpty())clearIntentions();
            if((method=="analyze"||method=="query")&&result.contains("result_counts")){beginHydration(method,result);return;}
            if(method=="analyze"||method=="query"){m_state=result;emit stateChanged();}
            if(method=="inspect"){result["occurrence_offset"]=request.params.value("occurrence_offset",0);m_detail=result;m_detailJson=resultJson;
                if(m_detailJson.endsWith('}')){m_detailJson.chop(1);m_detailJson+=QString(",\"occurrence_offset\":%1}").arg(request.params.value("occurrence_offset",0).toInt());}
                mark("inspect_detail_begin");emit detailChanged();mark("inspect_detail_end");}
            if(cancelRequested)result["cancel_requested"]=true;
            emit response(method,result);
        }
    }
public:
    bool exportPending() const { return !pendingExports.isEmpty(); }
    bool hasPendingOperations() const { return exportPending() || !methods.isEmpty() || m_busy; }
    Q_INVOKABLE QVariantMap diagnostics() const {
        return {{"pending",methods.size()},{"recent_responses",recentResponses.toVariantList()},
            {"backend",m_availability},{"error",m_error},{"stderr_tail",stderrTail}};
    }
    Bridge(){
        clock.start();
        tracePath=qEnvironmentVariable("SHOWPSISI_TRACE");
        if(!tracePath.isEmpty()){
            traceWriter=new QObject;
            traceWriter->moveToThread(&traceThread);
            connect(&traceThread,&QThread::finished,traceWriter,&QObject::deleteLater);
            traceThread.start();
        }
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
        transport=new BackendTransport;
        transport->moveToThread(&transportThread);
        connect(&transportThread,&QThread::finished,transport,&QObject::deleteLater);
        connect(transport,&BackendTransport::frame,this,[this](QJsonObject message,QVariantMap state,QVariantMap result,QVariantMap error,QString resultJson){
            mark("transport_frame_enter");receive(message,state,result,error,resultJson);mark("transport_frame_leave");
            if(message.value("event")=="progress")QMetaObject::invokeMethod(transport,"acknowledgeProgress",Qt::QueuedConnection);
        });
        connect(transport,&BackendTransport::started,this,[this](qint64 pid){backendPid=pid;m_availability="ready";emit availabilityChanged();mark("backend_started");});
        connect(transport,&BackendTransport::stderrRead,this,[this](QString text){stderrTail=(stderrTail+text).right(4096);});
        connect(transport,&BackendTransport::protocolError,this,[this](QString text){m_error=text;emit errorChanged();});
        connect(transport,&BackendTransport::stopped,this,[this](QString text){backendStopped(text+" "+stderrTail.trimmed());});
        transportThread.start();
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
        QMetaObject::invokeMethod(transport,"start",Qt::QueuedConnection,Q_ARG(QString,binary),Q_ARG(QStringList,arguments));
        mark("native_setup");
    }
    ~Bridge(){
        if(traceThread.isRunning()){
            // Drain ordered diagnostic writes before shutdown, never during GUI work.
            QMetaObject::invokeMethod(traceWriter,[]{},Qt::BlockingQueuedConnection);
            traceThread.quit();traceThread.wait();
        }
        if(transportThread.isRunning()){
            QMetaObject::invokeMethod(transport,"shutdown",Qt::BlockingQueuedConnection,Q_ARG(bool,exportPending()));
            transportThread.quit();transportThread.wait();
        }
    }
    QVariantMap progress()const{return m_progress;}
    bool paused()const{return m_paused;} bool pausePending()const{return m_pausePending;}
    bool loadingResults()const{return m_loadingResults;}
    QVariantMap remainingPages()const{QVariantMap result;for(auto i=pageOffsets.cbegin();i!=pageOffsets.cend();++i)result[i.key()]=i.value();return result;}
    Q_INVOKABLE void pauseAnalysis(){
        if(!m_busy||!activeAnalysis||m_cancelling||m_pausePending)return;
        m_pausePending=true;m_pauseTarget=!m_paused;emit pauseChanged();send(m_paused?"resume_analysis":"pause_analysis",{{"request_id",activeAnalysis}});
    }
    void beginHydration(QString method,QVariantMap result){
        ++hydrationEpoch;hydrationProgressClock.restart();hydrationCollections.clear();emit resultLoading();hydrationState=result;hydrationMethod=method;pageOffsets.clear();loadingPages.clear();
        hydrationQueue={"tables","services","events","history","table_history","diagnostics","density","table_groups"};
        for(const auto& name:hydrationQueue)hydrationState[name]=QVariantList{};
        m_loadingResults=true;m_busy=true;emit busyChanged();loadHydrationPage();
    }
    void finishHydration(){
        if(!m_loadingResults)return;mark("hydrate_finalize_begin");
        emit progressChanged();mark("hydration_progress_final");
        QHash<QString,QVariantList> groupMembers,selectedMembers;
        QSet<QString> truncatedGroups;
        for(const auto& value:hydrationCollections.value("table_groups")){const auto group=value.toMap();if(group.value("member_ids_truncated").toBool())truncatedGroups.insert(group.value("id").toString());}
        if(!truncatedGroups.isEmpty())for(const auto& rowValue:hydrationCollections.value("tables")){
            const auto row=rowValue.toMap();const auto key=row.value("table_group_id").toString();
            if(truncatedGroups.contains(key)){groupMembers[key].append(row.value("id"));if(row.value("selected_in_snapshot").toBool())selectedMembers[key].append(row.value("id"));}
        }
        auto& groups=hydrationCollections["table_groups"];
        for(auto& groupValue:groups){auto group=groupValue.toMap();if(group.value("member_ids_truncated").toBool()){
            const auto key=group.value("id").toString();group["section_ids"]=groupMembers.value(key);group["selected_section_ids"]=selectedMembers.value(key);group["member_ids_truncated"]=false;groupValue=group;
        }}
        for(auto it=hydrationCollections.cbegin();it!=hydrationCollections.cend();++it)hydrationState[it.key()]=it.value();
        mark("hydrate_assembled");m_state=hydrationState;awaitingPresentationEpoch=hydrationEpoch;emit stateChanged();mark("hydrate_published");
    }
    Q_INVOKABLE int resultEpoch()const{return hydrationEpoch;}
    Q_INVOKABLE void presentationReady(int epoch){
        if(epoch!=hydrationEpoch || epoch!=awaitingPresentationEpoch || !m_loadingResults)return;
        awaitingPresentationEpoch=-1;
        // Publish the bounded visible model, then allow an input/render turn before
        // enabling operations and starting the default inspection. Otherwise both
        // model replacement and inspector construction consume one GUI frame.
        QTimer::singleShot(50,this,[this,epoch]{
            if(epoch!=hydrationEpoch || !m_loadingResults)return;
            m_loadingResults=false;m_busy=false;mark("hydrate_enable_begin");emit busyChanged();mark("hydrate_enable_end");
            const auto method=hydrationMethod;hydrationMethod.clear();auto summary=m_state;
            for(const auto* key:{"tables","services","events","history","table_history","diagnostics","density","table_groups"})summary.remove(key);
            mark("hydrate_response_begin");emit response(method,summary);mark("hydrate_ready");
        });
    }
    Q_INVOKABLE void presentationFailed(int epoch,QString message){
        if(epoch!=hydrationEpoch || !m_loadingResults)return;
        const QString failedMethod=hydrationMethod.isEmpty()?"query_result":hydrationMethod;
        ++hydrationEpoch;awaitingPresentationEpoch=-1;hydrationQueue.clear();loadingPages.clear();pageOffsets.clear();hydrationCollections.clear();hydrationState.clear();hydrationMethod.clear();
        m_loadingResults=false;m_busy=false;m_state.clear();clearIntentions();emit resultLoading();emit stateChanged();emit busyChanged();
        m_error="Result presentation failed: "+message;emit errorChanged();
        emit response(failedMethod,{{"code","presentation_failed"},{"message",m_error}});
    }
    void loadHydrationPage(){
        if(!m_loadingResults)return;
        if(hydrationQueue.isEmpty()){finishHydration();return;}
        const QString collection=hydrationQueue.takeFirst();loadResultPage(collection,0);
    }
    void loadResultPage(QString collection,int offset){
        if(hydrationState.isEmpty())return;
        if(loadingPages.contains(collection))return;loadingPages.insert(collection);
        QVariantMap params={{"analysis_revision",hydrationState.value("analysis_revision")},{"collection",collection},{"offset",offset},{"limit",50},{"_epoch",hydrationEpoch}};
        if(!hydrationState.value("selected_packet").isNull())params["at_packet"]=hydrationState.value("selected_packet");
        mark("page_request_limit_"+QString::number(params.value("limit").toInt()));
        send("query_result",params);
    }
    Q_INVOKABLE void inspectOccurrences(int offset){
        if(m_busy||m_detail.isEmpty()||offset<0)return;
        QVariantMap params={{"id",m_detail.value("id")},{"analysis_revision",m_detail.value("analysis_revision")},{"occurrence_offset",offset}};
        if(!m_detail.value("native_table_at_packet").isNull())params["at_packet"]=m_detail.value("native_table_at_packet");
        send("inspect",params);
    }
    Q_INVOKABLE void loadMore(QString collection){if(!m_busy&&pageOffsets.contains(collection))loadResultPage(collection,pageOffsets.value(collection));}
    QString stateJson()const{
        auto metadata=m_state;
        if(metadata.value("response_mode")=="compact")for(const auto* key:{"tables","services","events","history","table_history","diagnostics","density","table_groups"})metadata.remove(key);
        return QString::fromUtf8(QJsonDocument::fromVariant(metadata).toJson(QJsonDocument::Compact));
    }
    QString detailJson()const{return m_detailJson;}
    QVariantMap state()const{return m_state;} QVariantMap detail()const{return m_detail;}
    void backendStopped(const QString& reason){
        if(m_availability=="disconnected")return;
        m_availability="disconnected";m_error="Backend disconnected. Restart the application. "+reason;
        ++generation;activeAnalysis=0;m_busy=false;m_cancelling=false;m_paused=false;m_pausePending=false;emit pauseChanged();
        methods.clear();m_loadingResults=false;hydrationState.clear();pageOffsets.clear();++hydrationEpoch;pendingExports.clear();emit exportPendingChanged();m_state.clear();clearIntentions();
        emit availabilityChanged();emit errorChanged();emit busyChanged();emit cancellingChanged();emit stateChanged();
    }
    bool inspecting()const{return m_inspecting;}
    bool comparing()const{return m_comparing;}
    bool cancelling()const{return m_cancelling;}
    bool available()const{return m_availability=="ready";}
    QString availability()const{return m_availability;}
    QString root()const{return m_root;} QString sample()const{return m_sample;}bool busy()const{return m_busy;}QString error()const{return m_error;}
    void attach(QQuickWindow*w){window=w;connect(w,&QQuickWindow::frameSwapped,this,[this]{
        if(!dataFrame&&!m_busy&&m_state.value("observations").toULongLong()>0){dataFrame=true;mark("first_paint");}
        if(!completeFrame&&!m_busy&&!m_cancelling&&m_state.value("complete").toBool()){completeFrame=true;mark("complete_paint");emit completedPaint();}
    },Qt::QueuedConnection);}
    Q_INVOKABLE void cancelAnalysis(){
        if(m_loadingResults){
            ++generation;++hydrationEpoch;clearTsRequests();hydrationQueue.clear();loadingPages.clear();pageOffsets.clear();
            const auto source=hydrationState.value("source");hydrationState.clear();hydrationCollections.clear();
            m_loadingResults=false;m_busy=false;m_cancelling=false;m_state={{"analysis_status","loading_cancelled"},{"source",source},{"complete",false}};
            clearIntentions();emit stateChanged();emit busyChanged();emit cancellingChanged();
            emit response("cancel_result_loading",{{"message","Result loading stopped. Analyze again to load a complete workspace."}});return;
        }
        if(!available()||!m_busy||m_cancelling||!activeAnalysis)return;
        m_cancelling=true;m_state.clear();emit stateChanged();
        // Invalidate every outstanding evidence/edit intention, retaining only
        // the original scan whose terminal response must still be observed.
        const auto analyze=methods.value(activeAnalysis);clearTsRequests();methods.insert(activeAnalysis,analyze);
        clearIntentions();emit cancellingChanged();mark("cancel_requested");
        send("cancel_analysis",{{"request_id",activeAnalysis}});
    }
    Q_INVOKABLE void send(QString method,QVariantMap params={}){
        if(m_availability=="disconnected"||!transport){
            backendStopped("Backend is not running. Check SHOWPSISI_CORE.");return;
        }
        if(m_busy&&method!="cancel_analysis"&&method!="pause_analysis"&&method!="resume_analysis"&&!(method=="query_result"&&m_loadingResults))return;
        if(method=="cancel_analysis"&&(!m_busy||!m_cancelling))return;
        if(!m_error.isEmpty()){m_error.clear();emit errorChanged();}
        int id=++sequence;
        if(method=="analyze"){
            ++generation;clearTsRequests();activeAnalysis=id;
            m_busy=true;m_cancelling=false;m_progress.clear();emit progressChanged();m_paused=false;m_pausePending=false;emit pauseChanged();
            dataFrame=completeFrame=false;emit busyChanged();emit cancellingChanged();mark("analyze_requested");
        }
        if(method=="inspect"){if(!params.contains("occurrence_offset"))params["occurrence_offset"]=0;params["occurrence_limit"]=50;latestInspect=id;const bool hadDetail=!m_detail.isEmpty(),wasInspecting=m_inspecting;m_detail.clear();m_detailJson="{}";m_inspecting=true;if(hadDetail)emit detailChanged();if(!wasInspecting)emit inspectingChanged();}
        if(method=="query"){latestQuery=id;latestInspect=latestPreview=latestTopology=0;const bool hadDetail=!m_detail.isEmpty(),wasInspecting=m_inspecting;m_detail.clear();m_detailJson="{}";m_inspecting=false;if(hadDetail)emit detailChanged();if(wasInspecting)emit inspectingChanged();}
        if(method=="query_topology")latestTopology=id;
        if(method=="import_dvbi"){latestDvbiImport=id;latestDvbiQuery=latestDvbiInspect=0;}
        if(method=="query_dvbi")latestDvbiQuery=id;
        if(method=="inspect_dvbi")latestDvbiInspect=id;
        if(method=="preview_rename")latestPreview=id;
        if(method=="diff_snapshots"){latestComparison=id;m_comparing=true;emit comparingChanged();}
        if(method=="analyze"||method=="query")params["response_mode"]="compact";
        methods.insert(id,{method,generation,params});
        params.remove("_epoch");
        if(method=="export"){pendingExports.insert(id);emit exportPendingChanged();}
        QJsonObject request{{"id",id},{"method",method},{"params",QJsonObject::fromVariantMap(params)}};
        QByteArray wire=QJsonDocument(request).toJson(QJsonDocument::Compact)+'\n';
        QMetaObject::invokeMethod(transport,"write",Qt::QueuedConnection,Q_ARG(QByteArray,wire));
    }
    Q_INVOKABLE QVariantMap lockState() const {
#ifdef Q_OS_WIN
        return {{"num",bool(GetKeyState(VK_NUMLOCK)&1)},{"scroll",bool(GetKeyState(VK_SCROLL)&1)}};
#else
        return {};
#endif
    }
    Q_INVOKABLE void mark(QString event){
        if(!traceWriter)return;
        QJsonObject value{{"event",event},{"ms",clock.nsecsElapsed()/1e6},{"wall_ms",double(QDateTime::currentMSecsSinceEpoch())},{"process_cpu_ms",1000.0*std::clock()/CLOCKS_PER_SEC},{"backend_pid",double(backendPid)}};
#ifdef Q_OS_LINUX
        timespec threadTime{};
        if(clock_gettime(CLOCK_THREAD_CPUTIME_ID,&threadTime)==0)value["gui_thread_cpu_ms"]=threadTime.tv_sec*1000.0+threadTime.tv_nsec/1e6;
#endif
        const auto line=QJsonDocument(value).toJson(QJsonDocument::Compact)+'\n';
        const auto path=tracePath;
        QMetaObject::invokeMethod(traceWriter,[path,line]{
            QFile file(path);if(file.open(QIODevice::Append))file.write(line);
        },Qt::QueuedConnection);
    }
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
    Q_INVOKABLE QStringList loadRecentFiles(){return layoutSettings()->value("workbenchRecentFiles").toStringList().mid(0,10);}
    Q_INVOKABLE bool saveRecentFiles(QStringList paths){auto settings=layoutSettings();settings->setValue("workbenchRecentFiles",paths.mid(0,10));settings->sync();return settings->status()==QSettings::NoError;}
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
    Q_INVOKABLE void testResult(QString text){if(traceWriter)QMetaObject::invokeMethod(traceWriter,[]{},Qt::BlockingQueuedConnection);QSaveFile f(qEnvironmentVariable("SHOWPSISI_TEST_RESULT"));const auto bytes=text.toUtf8();if(f.open(QIODevice::WriteOnly)&&f.write(bytes)==bytes.size()&&f.commit())mark("ui_test_done");else mark("ui_test_result_failed");}
signals:
    void resultLoading();void resultPage(QString collection,QString json);
    void progressChanged();void pauseChanged();void stateChanged();void detailChanged();void busyChanged();void exportPendingChanged();void cancellingChanged();void availabilityChanged();void workspaceInvalidated();void inspectingChanged();void comparingChanged();void errorChanged();void response(QString method,QVariantMap result);void completedPaint();
};
int main(int argc,char**argv){
#ifdef Q_OS_WIN
    // Presence, not ownership, protects every Qt/core instance from installer
    // replacement. Keep the handle until all application objects are destroyed.
    struct ApplicationLifetime {
        HANDLE handle=CreateMutexW(nullptr,FALSE,L"Local\\ShowPsiSi.ApplicationLifetime");
        ~ApplicationLifetime(){if(handle)CloseHandle(handle);}
    } applicationLifetime;
    if(!applicationLifetime.handle){
        MessageBoxW(nullptr,L"ShowPsiSi could not create its installation safety guard. The application will not start.",L"ShowPsiSi startup error",MB_OK|MB_ICONERROR);
        return 2;
    }
#endif
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
    app.setOrganizationName("ShowPsiSi");app.setApplicationName("ShowPsiSi");app.setApplicationVersion(QStringLiteral(SHOWPSISI_VERSION));QQuickStyle::setStyle("Basic");
    Bridge bridge;ReleaseUpdater updater;AgentDebug uiAgent;QQmlApplicationEngine engine;engine.rootContext()->setContextProperty("core",&bridge);
    engine.rootContext()->setContextProperty("uiAgent",&uiAgent);
    updater.setInstallGuard([&bridge] { return !bridge.hasPendingOperations(); });
    QObject::connect(&updater,&ReleaseUpdater::installerStarted,&app,&QCoreApplication::quit,Qt::QueuedConnection);
    engine.rootContext()->setContextProperty("appUpdater",&updater);
    engine.loadFromModule("ShowPsiSi","Main");if(engine.rootObjects().isEmpty())return 1;
    auto window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());
    uiAgent.setTrace([&bridge](const QString& value) { bridge.mark(value); });
    bridge.attach(window);uiAgent.attach(window);return app.exec();
}
#include "main.moc"

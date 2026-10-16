#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QQuickStyle>
#include <QProcess>
#include <QJsonDocument>
#include <QJsonObject>
#include <QFile>
#include <QDir>
#include <QElapsedTimer>
#include <QTimer>
#include <QDateTime>
#include <QMouseEvent>
#include <QQuickItem>

class Bridge:public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantMap state READ state NOTIFY stateChanged)
    Q_PROPERTY(QVariantMap detail READ detail NOTIFY detailChanged)
    Q_PROPERTY(QString root READ root CONSTANT)
    Q_PROPERTY(QString sample READ sample CONSTANT)
    Q_PROPERTY(bool busy READ busy NOTIFY busyChanged)
    Q_PROPERTY(QString error READ error NOTIFY errorChanged)
    QProcess process;QByteArray buffer;QVariantMap m_state,m_detail;QString m_root,m_sample,m_error;bool m_busy=false;
    QElapsedTimer clock;int sequence=0;QHash<int,QString> methods;bool dataFrame=false,completeFrame=false;QQuickWindow* window=nullptr;
public:
    Bridge(){
        clock.start();m_root=qEnvironmentVariable("SHOWPSISI_ROOT",QDir::currentPath());m_sample=qEnvironmentVariable("SHOWPSISI_SAMPLE",m_root+"/samples/generated/lab.ts");
        connect(&process,&QProcess::readyReadStandardOutput,this,[this]{
            buffer+=process.readAllStandardOutput();int nl;
            while((nl=buffer.indexOf('\n'))>=0){auto doc=QJsonDocument::fromJson(buffer.left(nl));buffer.remove(0,nl+1);QJsonObject msg=doc.object();
                if(msg.contains("event")){m_state=msg["state"].toObject().toVariantMap();emit stateChanged();}
                else {int id=msg["id"].toInt();QString method=methods.take(id);
                    if(msg.contains("error")){m_error=msg["error"].toObject()["message"].toString();emit errorChanged();emit response(method,msg["error"].toObject().toVariantMap());}
                    else {QVariantMap result=msg["result"].toObject().toVariantMap();
                        if(method=="analyze"||method=="query"){m_state=result;emit stateChanged();}
                        if(method=="inspect"){m_detail=result;emit detailChanged();}
                        emit response(method,result);
                    }
                    if(method=="analyze"){m_busy=false;emit busyChanged();mark("scan_response");}
                }
            }
        });
        connect(&process,&QProcess::errorOccurred,this,[this]{m_error=process.errorString();m_busy=false;emit errorChanged();emit busyChanged();});
        process.start(qEnvironmentVariable("SHOWPSISI_CORE",m_root+"/build/bin/showpsisi-core.exe"),{"--root",m_root});
        mark("native_setup");
    }
    ~Bridge(){process.closeWriteChannel();if(!process.waitForFinished(1000)){process.kill();process.waitForFinished(1000);}}
    QVariantMap state()const{return m_state;} QVariantMap detail()const{return m_detail;}
    QString root()const{return m_root;} QString sample()const{return m_sample;}bool busy()const{return m_busy;}QString error()const{return m_error;}
    void attach(QQuickWindow*w){window=w;connect(w,&QQuickWindow::frameSwapped,this,[this]{
        if(!dataFrame&&m_state.value("observations").toULongLong()>0){dataFrame=true;mark("first_paint");}
        if(!completeFrame&&m_state.value("complete").toBool()){completeFrame=true;mark("complete_paint");emit completedPaint();}
    },Qt::QueuedConnection);}
    Q_INVOKABLE void send(QString method,QVariantMap params={}){
        if(method=="analyze"){m_busy=true;m_error="";m_detail.clear();dataFrame=completeFrame=false;emit busyChanged();emit errorChanged();emit detailChanged();mark("analyze_requested");}
        int id=++sequence;methods[id]=method;QJsonObject request{{"id",id},{"method",method},{"params",QJsonObject::fromVariantMap(params)}};
        process.write(QJsonDocument(request).toJson(QJsonDocument::Compact)+'\n');
    }
    Q_INVOKABLE void mark(QString event){QString path=qEnvironmentVariable("SHOWPSISI_TRACE");if(path.isEmpty())return;QFile file(path);if(file.open(QIODevice::Append)){QJsonObject value{{"event",event},{"ms",clock.nsecsElapsed()/1e6},{"wall_ms",double(QDateTime::currentMSecsSinceEpoch())}};file.write(QJsonDocument(value).toJson(QJsonDocument::Compact)+'\n');}}
    Q_INVOKABLE QString env(QString name){return qEnvironmentVariable(name.toUtf8().constData());}
    Q_INVOKABLE QString localPath(QUrl url){return url.toLocalFile();}
    Q_INVOKABLE QString json(QVariant value){return QString::fromUtf8(QJsonDocument::fromVariant(value).toJson(QJsonDocument::Indented));}
    Q_INVOKABLE void capture(QString path){if(window){QDir().mkpath(QFileInfo(path).absolutePath());bool ok=window->grabWindow().save(path);mark(ok?"screenshot_saved":"screenshot_failed");}}
    Q_INVOKABLE bool click(QString name){if(!window)return false;std::function<QQuickItem*(QQuickItem*)> find=[&](QQuickItem* p)->QQuickItem*{if(p->objectName()==name)return p;for(auto c:p->childItems())if(auto found=find(c))return found;return nullptr;};auto item=find(window->contentItem());if(!item||!item->isVisible()||!item->isEnabled())return false;QPointF pos=item->mapToScene(QPointF(item->width()/2,item->height()/2));QMouseEvent press(QEvent::MouseButtonPress,pos,pos,window->mapToGlobal(pos.toPoint()),Qt::LeftButton,Qt::LeftButton,Qt::NoModifier);QCoreApplication::sendEvent(window,&press);QMouseEvent release(QEvent::MouseButtonRelease,pos,pos,window->mapToGlobal(pos.toPoint()),Qt::LeftButton,Qt::NoButton,Qt::NoModifier);QCoreApplication::sendEvent(window,&release);return true;}
    Q_INVOKABLE void testResult(QString text){QFile f(qEnvironmentVariable("SHOWPSISI_TEST_RESULT"));if(f.open(QIODevice::WriteOnly))f.write(text.toUtf8());mark("ui_test_done");}
signals:
    void stateChanged();void detailChanged();void busyChanged();void errorChanged();void response(QString method,QVariantMap result);void completedPaint();
};
int main(int argc,char**argv){
    QGuiApplication app(argc,argv);app.setApplicationName("ShowPsiSi");QQuickStyle::setStyle("Basic");
    Bridge bridge;QQmlApplicationEngine engine;engine.rootContext()->setContextProperty("core",&bridge);
    engine.loadFromModule("ShowPsiSi","Main");if(engine.rootObjects().isEmpty())return 1;
    bridge.attach(qobject_cast<QQuickWindow*>(engine.rootObjects().first()));return app.exec();
}
#include "main.moc"

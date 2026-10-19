import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "qrc:/shared/workbench.js" as Shared

Item {
    id: pane
    required property var host
    property var metadata: ({})
    property var documentData: ({})
    property var inspection: ({})
    property string operation: ""
    readonly property bool busy: operation !== ""
    readonly property bool ready: core.available && !core.busy && !core.exportPending && !host.exporting && !busy
    property string error: ""
    property bool stale: false
    property string selection: ""
    property string focused: ""
    property var expanded: ({})
    property var limits: ({})
    property var activeEvidence: null
    property var resolution: ({})
    property var intent: ({})
    property var backStack: []
    property string navigation: "Services"
    property string view: "Summary"
    property var selectedNode: (documentData.nodes || []).find(function(n){return n.node_id===selection;}) || null
    property var sources: selectedNode && Shared.workbench.dvbiEvidence ? Shared.workbench.dvbiEvidence(selectedNode) : []
    property var rowModel: Shared.workbench.dvbiRows ? Shared.workbench.dvbiRows(documentData,search.text,expanded,limits) : ({rows:[]})
    property var rows: rowModel.rows || []
    readonly property bool hasDocument: !!metadata.document_revision
    readonly property string documentKey: [metadata.document_revision,(metadata.source || {}).sha256].join(":")
    function identity(node){return Shared.workbench.dvbiIdentity ? Shared.workbench.dvbiIdentity(node) : "";}
    function pathValue(){return inputPath.text;}
    function clone(value) { return JSON.parse(JSON.stringify(value)); }
    function validate(value, revision, sha) {
        if (!Shared.workbench.validateDvbi) return "DVB-I presentation helpers are unavailable.";
        return Shared.workbench.validateDvbi(value,revision,sha);
    }
    function importDocument(path) {
        if(!ready || !path.trim()) return;
        inputPath.text=path;error="";operation="import";
        intent={revision:metadata.document_revision || 0};
        core.send("import_dvbi",{path:path,profile:"etsi-ts-103770-v1.2.1",expected_document_revision:intent.revision});
    }
    function loadNodes(append) {
        if(!ready || !hasDocument || stale)return;
        let offset=append ? (documentData.page || {}).next_offset : 0;
        if(offset===null || offset===undefined)return;
        operation="query";error="";intent={revision:metadata.document_revision,sha:metadata.source.sha256,offset:offset};
        core.send("query_dvbi",{document_revision:intent.revision,offset:offset,limit:500});
    }
    function point() {return {key:documentKey,selection:selection,focused:focused,expanded:expanded,limits:limits,search:search.text,navigation:navigation,view:view,evidence:activeEvidence,resolution:resolution,inspection:inspection,scroll:semanticList.contentY};}
    function remember() {backStack=backStack.concat([point()]).slice(-64);}
    function back() {
        if(busy || !backStack.length)return;
        let stack=backStack.slice(),p=stack.pop();backStack=stack;
        if(p.key!==documentKey){error="This navigation point belongs to a replaced document.";return;}
        selection=p.selection;focused=p.focused;expanded=p.expanded;limits=p.limits;search.text=p.search;navigation=p.navigation;view=p.view;
        activeEvidence=p.evidence;resolution=p.resolution;inspection=p.inspection;
        Qt.callLater(function(){semanticList.contentY=p.scroll;focusNode(focused);highlightSource();});
    }
    function selectNode(id, keep) {
        if(busy)return;
        if(!(documentData.nodes || []).some(function(n){return n.node_id===id;}))return;
        if(keep && (selection!==id || activeEvidence))remember();
        selection=id;focused=id;activeEvidence=null;resolution={};inspection={};view="Summary";navigation="Services";
        if(!stale)error="";
    }
    function focusNode(id) {
        let i=rows.findIndex(function(r){return r.node && r.node.node_id===id;});
        if(i>=0){focused=id;semanticList.currentIndex=i;semanticList.positionViewAtIndex(i,ListView.Contain);semanticList.forceActiveFocus();}
    }
    function toggle(row) {
        if(!row || !row.has_children || search.text.trim())return;
        let x=Object.assign({},expanded);x[row.node.node_id]=!row.expanded;expanded=x;
    }
    function activate(row) {
        if(row.more){let x=Object.assign({},limits),key=row.parent_id || "$roots";x[key]=(x[key] || 100)+100;limits=x;return;}
        selectNode(row.node.node_id,true);
    }
    function openSource(ref, keep) {
        if(!ready || stale || !ref)return;
        if(ref.document_revision!==metadata.document_revision || ref.source_sha256!==metadata.source.sha256){error="This source belongs to a replaced document.";return;}
        if(keep!==false)remember();
        activeEvidence=ref;resolution={};inspection={};
        let offset=Number.isInteger(ref.original_byte_offset) ? Math.floor(ref.original_byte_offset/4096)*4096 : 0;
        inspectElement(ref.element_id,offset,0,false,"Element");
    }
    function inspectElement(id, offset, childOffset, keep, targetView) {
        if(!ready || stale || !hasDocument)return;
        if(keep){remember();activeEvidence=null;resolution={};inspection={};}
        operation="inspect";error="";
        intent={revision:metadata.document_revision,sha:metadata.source.sha256,id:id || "e0",offset:offset || 0,childOffset:childOffset || 0};
        if(targetView)view=targetView;
        core.send("inspect_dvbi",{document_revision:intent.revision,element_id:intent.id,source_offset:intent.offset,source_limit:4096,child_offset:intent.childOffset,child_limit:200});
    }
    function retrySource() {
        if(!ready || stale || !hasDocument || !intent.id)return;
        inspectElement(intent.id,intent.offset,intent.childOffset,false,view);
    }
    function rootSource() {if(!ready || stale || !hasDocument)return;navigation="XML";inspectElement("e0",0,0,true,"Element");}
    function childSource(child) {
        if(!child)return;
        let offset=Number.isInteger(child.original_byte_offset) ? Math.floor(child.original_byte_offset/4096)*4096 : 0;
        inspectElement(child.element_id,offset,0,true,"Element");
    }
    function pageSource(delta) {
        let original=inspection.original_source || {}, next=Math.max(0,original.offset+delta*4096);
        if(next>=original.total && delta>0)return;
        inspectElement((inspection.element || {}).element_id,next,(inspection.child_page || {}).offset || 0,false,view);
    }
    function jumpSource() {
        let e=inspection.element || {};
        if(Number.isInteger(e.original_byte_offset))inspectElement(e.element_id,Math.floor(e.original_byte_offset/4096)*4096,(inspection.child_page || {}).offset || 0,false,"XML");
    }
    function highlightSource() {
        if(view!=="XML")return;
        let position=(inspection.original_source || {}).element_start_character;
        Qt.callLater(function(){
            core.highlightXml(originalXml.textDocument,host.lightTheme);
            if(position!==null && position!==undefined){
                // QTextDocument normalizes line breaks for display. This cursor
                // conversion never changes original byte/line provenance.
                position=String((inspection.original_source || {}).text || "").slice(0,position).replace(/\r\n/g,"\n").replace(/\r/g,"\n").length;
                originalXml.cursorPosition=position;originalXml.select(position,position+1);}
            else originalXml.deselect();
        });
    }
    onViewChanged: highlightSource()
    Connections { target: host; function onLightThemeChanged(){pane.highlightSource();} }
    function response(method,result) {
        if(["import_dvbi","query_dvbi","inspect_dvbi"].indexOf(method)<0)return;
        result=clone(result);let expected=operation;operation="";
        if(!expected)return;
        if(result.message){error=result.message;return;}
        let issue=validate(result,method==="import_dvbi"?intent.revision+1:intent.revision,method==="import_dvbi"?undefined:intent.sha);
        if(issue){error=issue;stale=true;return;}
        if(method==="import_dvbi"){
            metadata=result;documentData={};inspection={};selection="";focused="";expanded={};limits={};activeEvidence=null;resolution={};backStack=[];stale=false;search.clear();view="Summary";navigation="Services";loadNodes(false);
        }else if(method==="query_dvbi"){
            try {documentData=intent.offset ? Shared.workbench.mergeDvbi(documentData,result) : result;} catch(e) {error=String(e);stale=true;return;}
            if(documentData.error){error=documentData.error;stale=true;return;}
            let x=Object.assign({},expanded);(documentData.nodes || []).forEach(function(n){if(!n.parent_id && x[n.node_id]===undefined)x[n.node_id]=true;});expanded=x;
            if(!focused && rows.length && rows[0].node)focused=rows[0].node.node_id;
        }else{
            if(!result.element || result.element.element_id!==intent.id){error="The XML element response does not match the request.";return;}
            inspection=result;
            if(activeEvidence)resolution=Shared.workbench.resolveDvbiEvidence(activeEvidence,result);
            else resolution={status:"resolved",precision:"element",path:result.element.path,line:result.element.line,column:result.element.column,line_precision:"element_start",message:"Original document element; line and byte marker locate its opening tag."};
            highlightSource();
        }
    }
    Connections {
        target:core
        function onResponse(method,result){pane.response(method,result);}
        function onAvailabilityChanged(){if(!core.available){operation="";error="Backend disconnected. Restart the application to continue.";stale=hasDocument;filePicker.close();}}
    }
    function state() {return {metadata:metadata,data:documentData,inspection:inspection,operation:operation,error:error,stale:stale,selected:selection,focused:focused,expanded:expanded,search:search.text,rows:rows,row_identities:rows.filter(function(r){return !!r.node;}).map(function(r){return {id:r.node.node_id,text:identity(r.node)};}),sources:sources,evidence:activeEvidence,resolution:resolution,view:view,navigation:navigation,back_depth:backStack.length,xml_selection:originalXml.selectedText};}
    function action(a) {
        if(a.name==="dvbi_import" && typeof a.path==="string")importDocument(a.path);
        else if(a.name==="dvbi_select")selectNode(a.id,true);
        else if(a.name==="dvbi_focus")focusNode(a.id);
        else if(a.name==="dvbi_toggle")toggle(rows.find(function(r){return r.node && r.node.node_id===a.id;}));
        else if(a.name==="dvbi_source" && sources[a.index])openSource(sources[a.index].ref || sources[a.index]);
        else if(a.name==="dvbi_root")rootSource();
        else if(a.name==="dvbi_child")childSource((inspection.child_summaries || []).find(function(c){return c.element_id===a.id;}));
        else if(a.name==="dvbi_children")inspectElement(inspection.element.element_id,inspection.original_source.offset,a.offset,false,"Element");
        else if(a.name==="dvbi_view" && ["Summary","Element","XML","Hex","JSON","Metadata"].indexOf(a.value)>=0){view=a.value;highlightSource();}
        else if(a.name==="dvbi_search" && typeof a.value==="string")search.text=a.value.slice(0,512);
        else if(a.name==="dvbi_more")loadNodes(true);
        else if(a.name==="dvbi_reload")loadNodes(false);
        else if(a.name==="dvbi_retry")retrySource();
        else if(a.name==="dvbi_back")back();
        else if(a.name==="dvbi_page")pageSource(a.delta);
        else if(a.name==="dvbi_jump")jumpSource();
        else return false;
        return true;
    }
    function focusSearch(){search.forceActiveFocus();search.selectAll();}
    function focusNext(){
        if(semanticList.activeFocus || search.activeFocus || xmlChildren.activeFocus){
            if(view==="Summary")sourcesList.forceActiveFocus();
            else if(view==="XML")originalXml.forceActiveFocus();
            else if(view==="Hex")originalHex.forceActiveFocus();
            else if(view==="JSON")inspectionJson.forceActiveFocus();
            else if(view==="Metadata")metadataJson.forceActiveFocus();
            else elementText.forceActiveFocus();
        }else if(navigation==="XML")xmlChildren.forceActiveFocus();else semanticList.forceActiveFocus();
    }
    function openDialog(){if(ready)filePicker.open();}
    FileDialog {id:filePicker;title:"Open local DVB-I XML";nameFilters:["XML metadata (*.xml)","All files (*)"];onAccepted:importDocument(core.localPath(selectedFile));}
    component Plain: Label {textFormat:Text.PlainText;color:host.ink;wrapMode:Text.WrapAnywhere;font.pixelSize:12}
    component Push: Button {
        id:button;implicitHeight:28;focusPolicy:Qt.StrongFocus
        contentItem:Plain {text:button.text;verticalAlignment:Text.AlignVCenter;horizontalAlignment:Text.AlignHCenter;opacity:button.enabled?1:.4;font.pixelSize:11;wrapMode:Text.NoWrap}
        background:Rectangle {color:button.hovered?host.hoverSurface:host.raised;border.color:button.activeFocus?host.blue:host.controlBorder;border.width:button.activeFocus?2:1;radius:2}
    }
    component TextInput: TextField {selectByMouse:true;color:host.ink;placeholderTextColor:host.muted;background:Rectangle {color:host.surface;border.color:parent.activeFocus?host.blue:host.controlBorder;radius:2}}
    component ReadText: TextArea {readOnly:true;selectByMouse:true;textFormat:TextEdit.PlainText;color:host.ink;wrapMode:TextEdit.WrapAnywhere;font.family:"monospace";font.pixelSize:12;background:Rectangle {color:host.surface} Accessible.role:Accessible.StaticText}
    ColumnLayout {
        anchors.fill:parent;spacing:6
        RowLayout {
            Layout.fillWidth:true;Layout.margins:10;spacing:8
            Plain {text:"LOCAL DVB-I XML";color:host.muted;font.pixelSize:11}
            TextInput {id:inputPath;objectName:"dvbiPath";Layout.fillWidth:true;implicitHeight:30;enabled:ready;placeholderText:"Choose a local UTF-8 XML service list";Accessible.name:"Local DVB-I XML path";onAccepted:importDocument(text)}
            Push {objectName:"dvbiOpen";text:"Open…";enabled:ready;onClicked:openDialog()}
            Push {objectName:"dvbiReload";text:"Reload objects";enabled:ready && hasDocument && !stale;onClicked:loadNodes(false)}
            Push {objectName:"dvbiImport";text:busy?"Loading…":"Import";enabled:ready && !!inputPath.text.trim();onClicked:importDocument(inputPath.text)}
        }
        Plain {Layout.leftMargin:12;Layout.rightMargin:12;Layout.fillWidth:true;text:"ETSI TS 103 770 V1.2.1 · local metadata declarations · no network fetch, playback or TS association · bounded import without asynchronous cancel";color:host.muted;font.pixelSize:11}
        Plain {Layout.leftMargin:12;Layout.rightMargin:12;Layout.fillWidth:true;visible:hasDocument;text:"Document revision "+metadata.document_revision+" · "+((metadata.source || {}).bytes || 0)+" bytes · "+((metadata.counts || {}).elements || 0)+" XML elements · "+((documentData.nodes || []).length)+" / "+((metadata.counts || {}).nodes || 0)+" semantic objects · "+(metadata.status || "");color:metadata.status==="unsupported"?host.warningColor:host.ink}
        Plain {objectName:"dvbiLoadedSource";Layout.leftMargin:12;Layout.rightMargin:12;Layout.fillWidth:true;visible:hasDocument;text:"Loaded original: "+((metadata.source || {}).path || "")+" · SHA-256 "+((metadata.source || {}).sha256 || "");color:host.muted;font.pixelSize:11;elide:Text.ElideMiddle;wrapMode:Text.NoWrap;Accessible.name:"Loaded document path and SHA-256; complete values are in Metadata"}
        Plain {objectName:"dvbiError";Layout.leftMargin:12;Layout.rightMargin:12;Layout.fillWidth:true;visible:!!error;text:error;color:host.warningColor}
        Push {objectName:"dvbiRetry";Layout.leftMargin:12;visible:!!error && !!intent.id && !stale;text:"Retry source";enabled:ready;onClicked:retrySource()}
        ProgressBar {Layout.fillWidth:true;Layout.preferredHeight:2;visible:busy;indeterminate:true}
        SplitView {
            Layout.fillWidth:true;Layout.fillHeight:true
            handle:Rectangle {implicitWidth:6;color:SplitHandle.pressed?host.blue:host.dividerColor}
            Rectangle {
                SplitView.preferredWidth:440;SplitView.minimumWidth:280;SplitView.maximumWidth:700;color:host.panel
                ColumnLayout {
                    anchors.fill:parent;anchors.margins:8;spacing:6
                    RowLayout {
                        Push {objectName:"dvbiServices";text:"Service list";onClicked:navigation="Services"}
                        Push {objectName:"dvbiXmlTree";text:"XML tree";enabled:ready && hasDocument && !stale;onClicked:rootSource()}
                        Item {Layout.fillWidth:true}
                        Push {objectName:"dvbiBack";text:"Back";enabled:!busy && backStack.length>0;onClicked:back()}
                    }
                    TextInput {id:search;objectName:"dvbiSearch";Layout.fillWidth:true;visible:navigation==="Services";placeholderText:"Search loaded objects";Accessible.name:"Search loaded DVB-I objects";maximumLength:512}
                    Plain {Layout.fillWidth:true;visible:navigation==="Services";text:"Search covers loaded objects only. Names and LCNs do not establish service identity.";color:host.muted;font.pixelSize:11}
                    ListView {
                        id:semanticList;objectName:"dvbiList";enabled:!busy;Layout.fillWidth:true;Layout.fillHeight:true;visible:navigation==="Services";clip:true;model:rows;currentIndex:-1;keyNavigationEnabled:true;activeFocusOnTab:true;boundsBehavior:Flickable.StopAtBounds
                        ScrollBar.vertical:ScrollBar{}
                        onCurrentIndexChanged:if(activeFocus && rows[currentIndex] && rows[currentIndex].node)focused=rows[currentIndex].node.node_id
                        Keys.onReturnPressed:if(rows[currentIndex])activate(rows[currentIndex])
                        Keys.onSpacePressed:if(rows[currentIndex])activate(rows[currentIndex])
                        Keys.onRightPressed:{let r=rows[currentIndex];if(r && r.has_children && !r.expanded)toggle(r);else if(r && r.expanded && rows[currentIndex+1] && rows[currentIndex+1].parent_id===r.node.node_id)focusNode(rows[currentIndex+1].node.node_id);}
                        Keys.onLeftPressed:{let r=rows[currentIndex];if(r && r.expanded)toggle(r);else if(r && r.parent_id)focusNode(r.parent_id);}
                        delegate:ItemDelegate {
                            required property var modelData;required property int index
                            width:semanticList.width;height:60;leftPadding:8+modelData.depth*16
                            objectName:modelData.more?"dvbiBranchMore_"+index:"dvbiNode_"+modelData.node.node_id
                            Accessible.name:modelData.more?"Show more children":modelData.node.label+" · "+identity(modelData.node)+" · "+modelData.node.object_type
                            background:Rectangle {color:!modelData.more && modelData.node.node_id===selection?host.selectionSurface:parent.hovered?host.hoverSurface:host.panel;border.color:semanticList.activeFocus && semanticList.currentIndex===index?host.blue:"transparent";border.width:2}
                            contentItem:RowLayout {
                                Plain {text:modelData.more?"+":modelData.has_children?(modelData.expanded?"▾":"▸"):"·";Layout.preferredWidth:15;MouseArea{anchors.fill:parent;enabled:!!modelData.has_children;onClicked:toggle(modelData)}}
                                ColumnLayout {spacing:1;Layout.fillWidth:true
                                    Plain {text:modelData.more?"Show "+modelData.remaining+" more children":modelData.node.label;Layout.fillWidth:true;elide:Text.ElideRight;wrapMode:Text.NoWrap}
                                    Plain {visible:!modelData.more;text:modelData.more?"":identity(modelData.node)+"\n"+modelData.node.object_type+" · "+Shared.workbench.topologyStatus(modelData.node);Layout.fillWidth:true;elide:Text.ElideRight;maximumLineCount:2;color:host.muted;font.pixelSize:11}
                                }
                            }
                            onClicked:{semanticList.currentIndex=index;semanticList.forceActiveFocus();activate(modelData);}
                        }
                        Plain {anchors.centerIn:parent;width:parent.width-24;visible:!rows.length;text:!hasDocument?"Import a local XML document to inspect its declarations.":metadata.status==="unsupported"?"Unsupported namespace/root. No semantic mapping was fabricated. Open XML tree for all retained elements.":search.text?"No loaded objects match.":"No semantic objects loaded.";color:host.muted}
                    }
                    Push {objectName:"dvbiMore";visible:navigation==="Services" && !!(documentData.page || {}).has_more;Layout.fillWidth:true;text:"Load more objects ("+(documentData.nodes || []).length+" / "+((documentData.page || {}).total || 0)+")";enabled:ready && !stale;onClicked:loadNodes(true)}
                    ColumnLayout {
                        visible:navigation==="XML";Layout.fillWidth:true;Layout.fillHeight:true
                        Plain {Layout.fillWidth:true;text:(inspection.element || {}).path || "Loading document root…";color:host.muted;font.pixelSize:11;maximumLineCount:3;elide:Text.ElideMiddle}
                        RowLayout {
                            Push {text:"Root";enabled:ready && !stale;onClicked:rootSource()}
                            Push {objectName:"dvbiParent";text:"Parent";enabled:ready && !!(inspection.element || {}).parent_id && !stale;onClicked:inspectElement(inspection.element.parent_id,0,0,true,"Element")}
                            Plain {text:((inspection.child_page || {}).total || 0)+" children";color:host.muted}
                        }
                        ListView {
                            id:xmlChildren;objectName:"dvbiChildren";Layout.fillWidth:true;Layout.fillHeight:true;model:inspection.child_summaries || [];clip:true;activeFocusOnTab:true;keyNavigationEnabled:true;ScrollBar.vertical:ScrollBar{}
                            Keys.onReturnPressed:childSource(model[currentIndex])
                            delegate:ItemDelegate {required property var modelData;required property int index;width:xmlChildren.width;height:42;objectName:"dvbiChild_"+modelData.element_id;Accessible.name:modelData.qualified_name+" at line "+modelData.line
                                contentItem:Plain {text:(modelData.has_children?"▸ ":"· ")+modelData.qualified_name+" · line "+modelData.line+"\n"+modelData.namespace;elide:Text.ElideRight;maximumLineCount:2;font.pixelSize:11}
                                background:Rectangle {color:parent.hovered?host.hoverSurface:host.panel;border.color:xmlChildren.activeFocus && xmlChildren.currentIndex===index?host.blue:"transparent"}
                                onClicked:{xmlChildren.currentIndex=index;childSource(modelData);}
                            }
                        }
                        RowLayout {
                            Push {objectName:"dvbiChildrenPrevious";text:"Previous";enabled:ready && (inspection.child_page || {}).offset>0;onClicked:inspectElement(inspection.element.element_id,inspection.original_source.offset,Math.max(0,inspection.child_page.offset-200),false,"Element")}
                            Push {objectName:"dvbiChildrenNext";text:"Next children";enabled:ready && !!(inspection.child_page || {}).has_more;onClicked:inspectElement(inspection.element.element_id,inspection.original_source.offset,inspection.child_page.next_offset,false,"Element")}
                        }
                    }
                }
            }
            Rectangle {
                SplitView.fillWidth:true;SplitView.minimumWidth:360;color:host.panel
                ColumnLayout {
                    anchors.fill:parent;anchors.margins:10;spacing:7
                    RowLayout {Layout.fillWidth:true;spacing:4
                        Repeater {model:["Summary","Element","XML","Hex","JSON","Metadata"];Push {required property string modelData;objectName:"dvbiView_"+modelData;text:modelData;enabled:modelData==="Summary"||modelData==="Metadata"||!!inspection.element;onClicked:{view=modelData;highlightSource();}}}
                        Item {Layout.fillWidth:true}
                    }
                    Plain {Layout.fillWidth:true;visible:!!inspection.element && view!=="Summary";text:(resolution.message || "Original XML element")+"\n"+((inspection.element || {}).path || "")+" · line "+((inspection.element || {}).line || "?")+", column "+((inspection.element || {}).column || "?")+" (element start)";color:host.muted;font.pixelSize:11;maximumLineCount:4;elide:Text.ElideMiddle}
                    ColumnLayout {
                        visible:view==="Summary";Layout.fillWidth:true;Layout.fillHeight:true
                        Plain {text:selectedNode?selectedNode.label:"Select an object or open XML tree";font.pixelSize:16;Layout.fillWidth:true}
                        Plain {text:selectedNode?selectedNode.object_type+" · "+Shared.workbench.topologyStatus(selectedNode):"Object selection does not activate a source. Every declaration remains announced-only.";color:host.muted;Layout.fillWidth:true}
                        ScrollView {Layout.fillWidth:true;Layout.fillHeight:true;clip:true;ReadText {text:selectedNode?JSON.stringify({identity:selectedNode.identity,attributes:selectedNode.attributes,unresolved_reasons:selectedNode.unresolved_reasons},null,2):"";Accessible.name:"Selected DVB-I semantic object"}}
                        Plain {text:sources.length+" source references · explicit element/attribute precision";color:host.muted}
                        ListView {
                            id:sourcesList;objectName:"dvbiSources";Layout.fillWidth:true;Layout.preferredHeight:Math.min(220,Math.max(60,sources.length*52));model:sources;clip:true;keyNavigationEnabled:true;activeFocusOnTab:true;ScrollBar.vertical:ScrollBar{}
                            Keys.onReturnPressed:if(sources[currentIndex])openSource(sources[currentIndex].ref || sources[currentIndex])
                            delegate:ItemDelegate {required property var modelData;required property int index;property var ref:modelData.ref || modelData;objectName:"dvbiSource_"+index;width:sourcesList.width;height:52;enabled:ready && !stale;Accessible.name:"Open "+ref.precision+" source "+ref.path
                                contentItem:Plain{text:ref.precision+" · line "+ref.line+" (element start)\n"+ref.path;maximumLineCount:2;elide:Text.ElideMiddle;font.pixelSize:11}
                                background:Rectangle{color:parent.hovered?host.hoverSurface:host.raised;border.color:sourcesList.activeFocus && sourcesList.currentIndex===index?host.blue:host.dividerColor}
                                onClicked:{sourcesList.currentIndex=index;openSource(ref);}
                            }
                        }
                    }
                    ScrollView {visible:view==="Element";Layout.fillWidth:true;Layout.fillHeight:true;clip:true
                        Column {width:parent.width;spacing:8
                            Plain {width:parent.width;text:(inspection.element || {}).qualified_name || "";font.pixelSize:16}
                            Repeater {model:(inspection.element || {}).attributes || [];Plain {required property var modelData;required property int index;width:parent.width;text:modelData.qualified_name+" = "+modelData.value+"\nNamespace: "+(modelData.namespace || "(none)");color:resolution.attribute_index===index?host.blue:host.ink}}
                            Plain {width:parent.width;text:"XML-normalized character data (original bytes are separate)";color:host.muted;font.pixelSize:11}
                            ReadText {id:elementText;width:parent.width;text:(inspection.element || {}).text || "";Accessible.name:"XML-normalized element character data"}
                            Push {text:"Browse child elements";onClicked:navigation="XML"}
                        }
                    }
                    RowLayout {visible:view==="XML"||view==="Hex";Layout.fillWidth:true
                        Push {objectName:"dvbiSourcePrevious";text:"Previous bytes";enabled:ready && (inspection.original_source || {}).offset>0;onClicked:pageSource(-1)}
                        Push {objectName:"dvbiSourceNext";text:"Next bytes";enabled:ready && !!(inspection.original_source || {}).has_more;onClicked:pageSource(1)}
                        Push {objectName:"dvbiSourceJump";text:"Element start";enabled:ready && !!inspection.element;onClicked:jumpSource()}
                    }
                    Plain {visible:view==="XML"||view==="Hex";Layout.fillWidth:true;color:host.muted;font.pixelSize:11;text:"Original file bytes "+((inspection.original_source || {}).offset || 0)+" + "+((inspection.original_source || {}).length || 0)+" / "+((inspection.original_source || {}).total || 0)+(view==="XML"?" · UTF-8 text bytes "+((inspection.original_source || {}).text_offset || 0)+" + "+((inspection.original_source || {}).text_length || 0)+", first line "+((inspection.original_source || {}).text_start_line || 1)+" · displayed line breaks normalized; marker is element start only":" · document bytes, not TS section offsets")}
                    ScrollView {visible:view==="XML";Layout.fillWidth:true;Layout.fillHeight:true;clip:true;ReadText {id:originalXml;objectName:"dvbiOriginalXml";persistentSelection:true;onActiveFocusChanged:if(activeFocus)pane.highlightSource();text:(inspection.original_source || {}).text || "";Accessible.name:"Original UTF-8 XML source page"}}
                    ScrollView {visible:view==="Hex";Layout.fillWidth:true;Layout.fillHeight:true;clip:true;ReadText {id:originalHex;objectName:"dvbiOriginalHex";text:((inspection.original_source || {}).data || "").replace(/(.{32})/g,"$1\n");Accessible.name:"Original document byte hex page"}}
                    ScrollView {visible:view==="JSON";Layout.fillWidth:true;Layout.fillHeight:true;clip:true;ReadText {id:inspectionJson;text:JSON.stringify(inspection,null,2);Accessible.name:"DVB-I inspection JSON"}}
                    ScrollView {visible:view==="Metadata";Layout.fillWidth:true;Layout.fillHeight:true;clip:true;ReadText {id:metadataJson;text:hasDocument?JSON.stringify(metadata,null,2):"No imported document";Accessible.name:"Document source, hash, profile, diagnostics and coverage"}}
                }
            }
        }
    }
}

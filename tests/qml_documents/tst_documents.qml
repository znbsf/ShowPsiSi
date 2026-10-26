import QtQuick
import QtQuick.Controls
import QtTest
import "../../ui/qt"
Item {
 width:1200;height:800
 DocumentWorkspace {
  id:workspace;anchors.fill:parent
  sectionComponent:Component{TextField{objectName:'documentEditor';text:parent.documentData.payload.value||''}}
  summaryComponent:Component{Label{text:'Summary'}}
  decodeComponent:Component{Label{text:parent.documentData.payload.value||''}}
 }
 TestCase {
  name:'DocumentWindowLifecycle';when:windowShown
  function init(){workspace.reset(String(Math.random()));}
  function test_close_restores_independent_context(){workspace.open('si','pat','PAT',{value:'PAT bytes'},false);var first=workspace.state.active;var editor=findChild(workspace.frames[first],'documentEditor');verify(editor!==null);editor.text='retained selection context';workspace.open('summary','summary','Summary',{},false);workspace.open('decoded','pat','Decode',{value:'native fields'},false);compare(workspace.state.items.length,3);workspace.close();workspace.close();compare(workspace.state.active,first);compare(findChild(workspace.frames[first],'documentEditor'),editor);compare(editor.text,'retained selection context');}
  function test_reuse_duplicate_and_cycle(){workspace.open('si','pmt','PMT',{},false);var first=workspace.state.active;workspace.open('si','pmt','PMT',{},false);compare(workspace.state.items.length,1);workspace.open('si','pmt','PMT',{},true);compare(workspace.state.items.length,2);workspace.cycle(false);compare(workspace.state.active,first);}
  function test_layout_does_not_recreate_content(){workspace.open('si','a','A',{},false);var first=workspace.state.active;var editor=findChild(workspace.frames[first],'documentEditor');workspace.open('summary','b','B',{},false);workspace.open('decoded','c','C',{},false);workspace.arrange('tile');compare(workspace.state.items[1].x,600);compare(workspace.state.items[0].mode,'normal');workspace.arrange('cascade');compare(workspace.state.items[1].x,24);compare(findChild(workspace.frames[first],'documentEditor'),editor);workspace.reset('different source');compare(workspace.state.items.length,0);}
 }
}

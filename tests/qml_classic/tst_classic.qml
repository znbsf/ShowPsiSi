import QtQuick
import QtQuick.Controls
import QtTest
import "../../ui/qt"
Item {
 width:1000;height:600
 QtObject {
  id:host
  property var state: ({available:true,busy:false,cancelling:false,canPause:false,paused:false,hasInput:false,complete:false,native:true,exporting:false,toolbar:true,status:true,tree:true,documentCount:0,features:{}})
  function classicState(){return state;}
 }
 ClassicFrame {id:frame;host:host;onCommand:function(name){commands.push(name);}}
 property var commands:[]
 TestCase {
  name:"ClassicFrameCommands";when:windowShown
  function init(){commands=[];host.state={available:true,busy:false,cancelling:false,canPause:false,paused:false,hasInput:false,complete:false,native:true,exporting:false,toolbar:true,status:true,tree:true,documentCount:0,features:{}};wait(20);}
  function tool(name){var control=findChild(frame,"classicTool:"+name);verify(control!==null);return control;}
  function test_empty_source_cannot_start(){compare(tool('start').enabled,false);mouseClick(tool('start'));compare(commands.length,0);mouseClick(tool('open'));compare(commands[0],'open');}
  function test_scan_controls_do_not_bypass_state(){host.state=Object.assign({},host.state,{hasInput:true,busy:true,canPause:true});wait(20);compare(tool('open').enabled,false);compare(tool('start').enabled,false);compare(tool('stop').enabled,true);compare(tool('pause').enabled,true);mouseClick(tool('pause'));compare(commands[0],'pause');host.state=Object.assign({},host.state,{cancelling:true});wait(20);compare(tool('pause').enabled,false);compare(tool('stop').enabled,false);}
  function test_tree_toggle_dispatch_and_checked_state(){compare(tool('tree').checked,true);mouseClick(tool('tree'));compare(commands[0],'tree');host.state=Object.assign({},host.state,{tree:false});wait(20);compare(tool('tree').checked,false);}
  function test_unsupported_output_disabled(){compare(tool('save').enabled,false);compare(tool('print').enabled,false);}
 }
}

import MonitorLedClassObject from "./MonitorLedClassObject";
/** @class MonitorLed */

class MonitorLed {
    classObject:   MonitorLedClassObject;
    ledText:       string;
    RUNNING_COLOR: string;
    PASS_COLOR:    string;
    FAIL_COLOR:    string;
    constructor() {
        this.classObject   = new MonitorLedClassObject();
        this.ledText       = "ready.";
        this.RUNNING_COLOR = "lightyellow";
        this.PASS_COLOR    = "lightgreen";
        this.FAIL_COLOR    = "#fb6666"; // lightred is not understood by CSS.  Whaaa... ??
    }

    setFail( fail_message : string ) {
        this.setLedBackgroundColor( this.FAIL_COLOR );
        this.setLedTextColor(       "white"         );
        this.setLedText(            fail_message    ); }
    
    setPass( pass_message : string ) {
        this.setLedBackgroundColor( this.PASS_COLOR );
        this.setLedTextColor(       "black"         );
        this.setLedText(            pass_message    ); }

    setLedBackgroundColor( newColor : string ) { this.classObject.background_color = newColor; }
    setLedTextColor(       newColor : string ) { this.classObject.color            = newColor; }
    setLedText(            newText  : string ) { this.ledText                      = newText ; }
}

export default MonitorLed;

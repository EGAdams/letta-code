import FetchRunner from "./FetchRunner";
import ILogObject       from "../abstract/ILogObject";
import LogObjectFactory from "./LogObjectFactory";
import Model            from "./Model";
import MonitorLed       from "./MonitorLed";
import SourceData       from "./SourceData";
import Stringifier      from "./Stringifier";
/** @class  MonitoredObject */
export default class MonitoredObject {
    object_view_id:     string;
    logObjects:         ILogObject[];
    model:              Model;
    logObjectFactory:   LogObjectFactory;
    monitorLed:         MonitorLed;
    stringifier:        Stringifier;
    constructor( config: { new_id: string | null, data_source_location: string | null; } ) {
        if ( config.new_id?.length === 0 ) { config.new_id = Math.floor( Math.random() * 1000 + 1000 ).toString(); }
        if ( config.new_id?.includes('_')) {
            this.object_view_id = config.new_id
        } else { this.object_view_id = `${ this.constructor.name }_${ config.new_id }`; }
        this.logObjectFactory  = new LogObjectFactory();
        this.logObjects        = [ this.logObjectFactory.createLogObject( "constructing...", this )];
        if ( config.data_source_location?.length === 0 && document.querySelector( '.data-source-location' )) { 
            config.data_source_location = document.querySelector( '.data-source-location' )?.innerHTML || "" }
        this.model             = new Model( new SourceData({ Runner: FetchRunner, url: config.data_source_location! }));
        this.monitorLed        = new MonitorLed();
        this.stringifier       = new Stringifier();
        const data_config        = { object_view_id: this.object_view_id, object_data: this.stringifier.stringify( this, 3, null, 2 )};
        this.model.insertObject( data_config, this ); } // xtra line of code, but more readable

    logUpdate( message : string ) {
        if ( !this.object_view_id ) {  console.log( "*** ERROR: object needs an id to log. ***" ); return; }
        if ( message.includes( "ERROR" )) { 
            this.monitorLed.setFail( message );
        } else if( message.includes( "finished" )) {
            this.monitorLed.setPass( message );
        } else { 
            this.monitorLed.setLedText( message ); }
        this.logObjects.push( this.logObjectFactory.createLogObject( message, this                   ));
        const data_config = { object_view_id: this.object_view_id, object_data: this.stringifier.stringify( this, 3, null, 2 )};
        this.model.updateObject( data_config, this                                                   ); }
    
    
    processQueryResult( _event: any, results: { data: string | any[]; } ) { if ( results.data.length > 0 ) { console.log( results.data ); }}
    getObjectViewId() { return this.object_view_id; }
}

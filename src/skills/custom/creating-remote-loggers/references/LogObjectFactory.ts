import ILogObject       from "../abstract/ILogObject";
import MonitoredObject from "./MonitoredObject.js";
/**
 * @description
 * creates log objects giving them a unique id,
 * time stamp, and determined calling method.
 *
 * @class LogObjectFactory
 */
class LogObjectFactory {
    someObject: unknown;
    constructor() { console.log( 'constructing LogObjectFactory object...' ); }

    createLogObject( messageArg: string, someObject: MonitoredObject ) {
        const time_now = Date.now();
        const random_number = Math.floor( Math.random() * 10000000000000 );
        const logObject: ILogObject = {
            timestamp: time_now,
            id:        `${ someObject.constructor.name }_${ random_number }_${ time_now }`,
            message:   messageArg,
            method:    this._getCallingMethod() };
        return logObject; }

    _getCallingMethod() {
        const obj = new Error();
        Error.captureStackTrace( obj, this._getCallingMethod );
        if ( obj.stack?.split( '\n' )[ 2 ].match( /at\s+\w+.(\w+)/ ) == null ) {
            return 'unknown'; }
        let split_stack = obj.stack.split( '\n' )[ 2 ];
        let split_stack_match = split_stack.match( /at\s+\w+.(\w+)/ );
        if ( !split_stack_match ) { return "no split_stack_match!"; }
        return split_stack_match[ 1 ];
    }
}

export default LogObjectFactory;

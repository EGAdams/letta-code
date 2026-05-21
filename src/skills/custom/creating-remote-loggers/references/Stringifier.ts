/** @class Stringifier */
export default class Stringifier {
    constructor() { }
    // replacer: ((this: any, key: string, value: any ) => any ) | null, ... notice the parentheses, these are needed.
    stringify ( val: any, depth: number, replacer: ((this: any, key: string, value: any ) => any ) | null, space?: string | number, onGetObjID?: ( val: object ) => string ): string {
        depth = isNaN( +depth ) ? 1 : depth;
        var recursMap = new WeakMap();
        function _build ( val: any, depth: number, o?: any, a?: boolean, r?: boolean ) {
            return !val || typeof val != 'object' ? val
                : ( r = recursMap.has( val ),
                    recursMap.set( val, true ),
                    a = Array.isArray( val ),
                    r ? ( o = onGetObjID && onGetObjID( val ) || null ) : JSON.stringify( val, function ( k, v ) { if ( a || depth > 0 ) { if ( replacer ) v = replacer( k, v ); if ( !k ) return ( a = Array.isArray( v ), val = v ); !o && ( o = a ? [] : {} ); o[ k ] = _build( v, a ? depth : depth - 1 ); } } ),
                    o === void 0 ? ( a ? [] : {} ) : o );
        }
        return JSON.stringify( _build( val, depth ), null, space );
    }
}    

// https://stackoverflow.com/questions/13861254/json-stringify-deep-objects/57193345#57193345 // typescript version

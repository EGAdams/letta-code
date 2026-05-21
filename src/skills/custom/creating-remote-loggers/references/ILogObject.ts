/**
 * @export
 * @interface ILogObject
*/
/**
 *
 * @description
 * An object that contains information about a logged event.  Hence, it is a log object.
 *
 * @property {string} id - A unique identifier for the logged event.
 * @property {number} timestamp - The timestamp of the logged event in milliseconds since the Unix epoch.
 * @property {string} message - The message associated with the logged event.
 * @property {string} method - The method or function that generated the logged event.
 */
export default interface ILogObject {
	id: string;
	timestamp: number; // timestamp in milliseconds since epoch
	message: string;
	method: string;
}

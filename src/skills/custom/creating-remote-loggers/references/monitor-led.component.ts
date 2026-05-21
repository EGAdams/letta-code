import type IQueryResultProcessor from "@/typescript_source/abstract/IQueryResultProcessor";
import FetchRunner from "@/typescript_source/concrete/FetchRunner";
import Model from "@/typescript_source/concrete/Model";
import ServerLedData from "@/typescript_source/concrete/ServerLedData";
import SourceData from "@/typescript_source/concrete/SourceData";
import { Component } from "@/utils";
import html from "./monitor-led.html";
import style from "./styles/main.css";

@Component({ html: html, style: style, properties: [] })
export class MonitorLed implements IWebComponent, IQueryResultProcessor {
  monitored_object_id = "";
  data_source_location: string | null = "";
  monitor_led_data: ServerLedData = new ServerLedData();

  // return an array containing the names of the attributes you want to observe.  Not sure why this is here yet.
  static observedAttributes() {}

  constructor(
    private $el: HTMLElement,
    private $host: Element,
  ) {
    this.data_source_location = $host.getAttribute(
      "data_source_location",
    ) as string;
  }

  /**
   * Invoked each time the custom element is appended into a document-connected element.
   * This will happen each time the node is moved, and may happen before the element's contents have been fully parsed.
   */
  connectedCallback() {
    // this.logUpdate( 'monitor-led connected' );
    this.render().start();
  }

  render() {
    this.$el.innerHTML = `
        <div class="monitor-led">${this.monitor_led_data.ledText}</div>
        `;
    const monitor_led = this.$el.querySelector<HTMLElement>(".monitor-led");
    monitor_led?.style.backgroundColor =
      this.monitor_led_data.classObject.background_color;
    monitor_led?.style.textAlign = this.monitor_led_data.classObject.text_align;
    monitor_led?.style.marginTop = this.monitor_led_data.classObject.margin_top;
    monitor_led?.style.color = this.monitor_led_data.classObject.color;
    return this;
  }

  /** Invoked each time the custom element is disconnected from the document's DOM. */
  disconnectedCallback() {
    console.log("monitor-led disconnected");
  }

  /** Invoked each time the custom element is moved to a new document. */
  adoptedCallback() {
    console.log("monitor-led moved");
  }

  /**
   * Invoked each time one of the custom element's attributes is added, removed, or changed.
   * Which attributes to notice change for is specified in a static get observedAttributes method
   *
   * @param name
   * @param oldValue
   * @param newValue
   */
  attributeChangedCallback(name: string, _oldValue: any, newValue: any) {
    const nameProp = name.replace(/-[a-zA-Z]/g, (found: string) =>
      found.slice(1).toUpperCase(),
    );
    (this as any)[nameProp] = newValue;
  }

  start() {
    // this.logUpdate( "monitor led component starting..." );
    const object_being_monitored = this.$host.getAttribute(
      "monitored_object_id",
    ) as string;
    const source_query_config = {
      object_view_id: object_being_monitored,
      object_data: {},
    };
    const model = new Model(
      new SourceData({ Runner: FetchRunner, url: this.data_source_location! }),
    );
    setInterval(() => {
      model.selectObject(source_query_config, this);
    }, 2500);
  }

  processQueryResult(_callbackObject: MonitorLed, query_result: any) {
    if (query_result.length < 15 || !JSON.parse(query_result).object_data) {
      return;
    }
    const data = JSON.parse(JSON.parse(query_result).object_data);
    if (Object.keys(data).length === 0) {
      this.render();
      return;
    }
    if (data.monitorLed) {
      this.monitor_led_data = data.monitorLed;
    }
    this.render();
    const object_being_monitored = this.$host.getAttribute(
      "monitored_object_id",
    ) as string;
    const the_number_part = object_being_monitored.match(/\d+/)?.[0]!;
    const the_name_part = object_being_monitored.replace(
      `_${the_number_part}`,
      "",
    );
    const event_name = `event-${this.kebabize(the_name_part)}-${the_number_part}`;
    data.noisy_component = this;
    const led_event = new CustomEvent(event_name, {
      bubbles: true,
      detail: data,
    });
    document.dispatchEvent(led_event);
  }

  kebabize(str: string) {
    return str
      .split("")
      .map((letter, idx) => {
        return letter.toUpperCase() === letter
          ? `${idx !== 0 ? "-" : ""}${letter.toLowerCase()}`
          : letter;
      })
      .join("");
  }
}

// Ref.: https://developer.mozilla.org/en-US/docs/Web/Web_Components/Using_custom_elements

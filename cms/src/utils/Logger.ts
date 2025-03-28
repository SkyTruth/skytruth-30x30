/**
 * Logger class for logging messages to the GCP via stdout.
 */
export default class Logger {

  /**
   * Function for logging INFO messages.
   * @param message Human Readable message
   * @param data JSON blob of data to be logged under jsonPayload
   */
  public static info(message: string, data: any = {}): void {
    data.severity = "INFO";
    Logger.parseMessage(message, data)
    Logger.log(console.log, data);
  }

  /**
   * Function for logging WARN messages.
   * @param message Human Readable message
   * @param data JSON blob of data to be logged under jsonPayload
   */
  public static warn(message: string, data: any = {}): void {
    data.severity = "WARNING";
    Logger.parseMessage(message, data)
    Logger.log(console.warn, data);
  }

  /**
   * Function for logging ERROR messages.
   * @param message Human Readable message
   * @param data JSON blob of data to be logged under jsonPayload
   */
  public static error(message: string, data: any = {}): void {
    data.severity = "ERROR";
    Logger.parseMessage(message, data)
    Logger.log(console.error, data);
  }

  /**
   * Function to write parsed log
   * @param loggerFn Function to be used to log the data 
   * @param data Proccesed JSON blob of data to be logged under jsonPayload
   */
  private static log(loggerFn: Function, data: any = {}): void {
    loggerFn(JSON.stringify({ data }));
  }

  /**
   * Helper function to parse message and data into a single string
   * @param message Human readable message
   * @param data JSON blob of data to be logged under jsonPayload
   * @returns 
   */
  private static parseMessage(message: string, data: any = {}): void {
    if (data.message) {
      data.message = message + ": " + data.message;
    } else {
      data.message = message;
    }
  }
}

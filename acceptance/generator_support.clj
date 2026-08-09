(ns acceptance.generator-support)

(defn exit! [status message]
  (binding [*out* *err*]
    (println message))
  (System/exit status))

(defmacro require-argument-count! [args expected message]
  `(when (not= ~expected (count ~args))
     (acceptance.generator-support/exit! 2 ~message)))

(defmacro with-error-exit [& body]
  `(try
     ~@body
     (catch Exception error#
       (acceptance.generator-support/exit! 1 (.getMessage error#)))))

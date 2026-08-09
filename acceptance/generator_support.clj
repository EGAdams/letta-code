(ns acceptance.generator-support)

(defmacro require-argument-count! [args expected message]
  `(when (not= ~expected (count ~args))
     (acceptance.generator/exit! 2 ~message)))

(defmacro with-error-exit [& body]
  `(try
     ~@body
     (catch Exception error#
       (acceptance.generator/exit! 1 (.getMessage error#)))))

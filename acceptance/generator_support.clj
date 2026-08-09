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

;; clj-mutate-manifest-begin
;; {:version 1, :tested-at "2026-08-08T22:38:15.24492385-04:00", :module-hash "-601010275", :forms [{:id "form/0/ns", :kind "ns", :line 1, :end-line nil, :hash "-123957801"} {:id "defn/exit!", :kind "defn", :line 3, :end-line nil, :hash "-1497667937"} {:id "defmacro/require-argument-count!", :kind "defmacro", :line 8, :end-line nil, :hash "-214449309"} {:id "defmacro/with-error-exit", :kind "defmacro", :line 12, :end-line nil, :hash "-1888924835"}]}
;; clj-mutate-manifest-end

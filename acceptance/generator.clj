(ns acceptance.generator
  (:require [babashka.fs :as fs]
            [cheshire.core :as json]
            [clojure.string :as str]
            [acceptance.generator-support :refer [require-argument-count!
                                                  with-error-exit]]))

(defn- sha256 [value]
  (let [digest (java.security.MessageDigest/getInstance "SHA-256")]
    (.update digest (.getBytes value java.nio.charset.StandardCharsets/UTF_8))
    (format "%064x" (java.math.BigInteger. 1 (.digest digest)))))

(defn- normalized-metadata-name [feature-path]
  (str (-> feature-path
           str/lower-case
           (str/replace #"[^a-z0-9]+" "-")
           (str/replace #"^-|-$" ""))
       ".json"))

(defn- generated-source [feature]
  (let [encoded (.encodeToString
                 (java.util.Base64/getEncoder)
                 (.getBytes (json/generate-string feature)
                            java.nio.charset.StandardCharsets/UTF_8))]
    (str "#!/usr/bin/env python3\n"
       "import base64\n"
       "import json\n\n"
       "from acceptance_runtime import run_feature\n\n"
       "FEATURE = json.loads(base64.b64decode(\"" encoded "\"))\n\n"
       "if __name__ == \"__main__\":\n"
       "    raise SystemExit(run_feature(FEATURE))\n")))

(defn- write-artifacts! [ir-path output-dir]
  (let [feature (json/parse-string (slurp ir-path) true)
        stem (fs/strip-ext (fs/file-name ir-path))
        feature-path (str "features/" stem ".feature")
        generated-path (fs/path output-dir (str stem "_acceptance_test.py"))
        source (generated-source feature)
        metadata-path (fs/path output-dir "metadata"
                               (normalized-metadata-name feature-path))
        generated-relative (str generated-path)]
    (fs/create-dirs output-dir)
    (fs/create-dirs (fs/parent metadata-path))
    (spit (str generated-path) source)
    (spit (str metadata-path)
          (str
           (json/generate-string
            {:schema_version 1
             :feature_path feature-path
             :ir_path ir-path
             :implementation_hash (str "sha256:" (sha256 source))
             :hash_scope "generated_files"
             :generated_files [generated-relative]}
            {:pretty true})
           "\n"))))

(defn -main [& args]
  (require-argument-count!
   args
   2
   "usage: acceptance-entrypoint-generator <json-ir> <generated-test-output>")
  (let [[ir-path output-dir] args]
    (with-error-exit
      (write-artifacts! ir-path output-dir))))

;; clj-mutate-manifest-begin
;; {:version 1, :tested-at "2026-08-08T22:38:14.634862499-04:00", :module-hash "-1550567680", :forms [{:id "form/0/ns", :kind "ns", :line 1, :end-line nil, :hash "448754370"} {:id "defn-/sha256", :kind "defn-", :line 8, :end-line nil, :hash "-1753099738"} {:id "defn-/normalized-metadata-name", :kind "defn-", :line 13, :end-line nil, :hash "1697226484"} {:id "defn-/generated-source", :kind "defn-", :line 20, :end-line nil, :hash "-25207106"} {:id "defn-/write-artifacts!", :kind "defn-", :line 33, :end-line nil, :hash "593465050"} {:id "defn/-main", :kind "defn", :line 57, :end-line nil, :hash "-810437510"}]}
;; clj-mutate-manifest-end

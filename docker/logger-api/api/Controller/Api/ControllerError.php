<?php
/** @class ControllerError */
class ControllerError {
    public function __construct() {
        $this->errorMessages = "";
        $this->errorHeader = "";
        $this->clean       = true;
    }

    public function addErrorMessage( $newErrorMessage ) {
        $this->errorMessages .= "\n " . $newErrorMessage;
        $this->clean = false;
    }

    public function setErrorHeader( $headerError ) {
        $this->errorHeader = $headerError;
    }

    public function getErrorHeader() {   return $this->errorHeader;  }
    public function getErrorMessages() { return $this->errorMessages; }
    public function isClean() {          return $this->clean;        }
}

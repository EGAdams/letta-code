<?php
define("PROJECT_ROOT_PATH", dirname( __DIR__, 1 ));
//define("PROJECT_ROOT_PATH", "joomla/prototype/local-php-api" );
// echo "project root path is: " . PROJECT_ROOT_PATH . "<br>";

// include main configuration file
// $project_root_path = PROJECT_ROOT_PATH . "/inc/config.php";
//require_once $project_root_path;

// include main configuration file
// echo "opening ".  PROJECT_ROOT_PATH . "/inc/config.php"; 
require_once PROJECT_ROOT_PATH . "/inc/config.php";
 
// include the base controller file
require_once PROJECT_ROOT_PATH . "/Controller/Api/BaseController.php";

// include the controller error file
require_once PROJECT_ROOT_PATH . "/Controller/Api/ControllerError.php";
 
// include the use model file
require_once PROJECT_ROOT_PATH . "/Model/ObjectModel.php";
?>

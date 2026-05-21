<?php
header( "Access-Control-Allow-Origin: *" );
require_once __DIR__ . "/inc/bootstrap.php";
require_once PROJECT_ROOT_PATH . "/Controller/Api/ObjectController.php";

$uri = parse_url($_SERVER["REQUEST_URI"], PHP_URL_PATH);
$uri = explode( "/", $uri );
$controller = new ObjectController( "monitored_objects" );

// Find the "object" index dynamically
$objectIndex = array_search("object", $uri);
if ($objectIndex === false || !isset($uri[$objectIndex + 1])) {
    header("HTTP/1.1 404 Not Found");
    exit();
}

$methodName = $uri[$objectIndex + 1] . "Action";
$controller->{ $methodName }();
?>

<?php
// echo "require_once config.php... <br>";
require_once  __DIR__  . "/../inc/config.php";
// echo "done requiring config.php. <br>";
class Database {
    protected $connection = null;
	public function __construct() {
        try {
            // echo "connecting to database ... <br>";
            // echo DB_HOST . "<br>" . DB_USERNAME . "<br>" . DB_PASSWORD . "<br>" . DB_DATABASE_NAME . "<br>";
            
            $this->connection = new mysqli( DB_HOST, DB_USERNAME, DB_PASSWORD, DB_DATABASE_NAME );
            // echo "done making connection. <br>";
			if ( mysqli_connect_errno()) { throw new DatabaseException( "Could not connect to database." ); }
		} catch ( Exception $e ) {
		    echo "*** ERROR: DatabaseException about to be thrown! *** <br>";
		    echo "\$e->getMessage(): " . $e->getMessage();
         
		    throw new DatabaseException( $e->getMessage()); }
	        // echo "done constructing Database object. <br>";
	}
    
	public function select( $query = "", $params = []) {
        try {
            $stmt = $this->executeStatement( $query, $params);
			$result = $stmt->get_result()->fetch_all( MYSQLI_ASSOC );
			$stmt->close();
			return $result;
		} catch ( Exception $e ) { throw new DatabaseException( $e->getMessage()); }
		return false;
	}
    
    public function insert( $query ) {
        try {
            // echo "query: " . $query . "<br>";
            
            $stmt = $this->executeStatement( $query );
            $stmt->close();
            return $stmt;
        } catch ( Exception $e ) {
            echo "*** ERROR: DatabaseException: ".$e->getMessage() ."<br>";
            throw new DatabaseException( $e->getMessage()); }
        return false;
    }

    public function delete( $query ) {
        try {
            $stmt = $this->executeStatement( $query );
            $stmt->close();
            return $stmt;
        } catch ( Exception $e ) { throw new DatabaseException( $e->getMessage()); }
        return false;
    }

    public function update( $query, $params = []) {
        try {
            $stmt = $this->executeStatement( $query, $params );
            $stmt->close();
            return $stmt;
        } catch ( Exception $e ) { throw new DatabaseException( $e->getMessage()); }
        return false;
    }
    
	private function executeStatement( $query = "", $params = []) {
		try {
            $stmt = $this->connection->prepare( $query );
			if ( $stmt === false ) { throw new DatabaseException( "Unable to do prepared statement: " . $query); }
			if ( $params ) { $stmt->bind_param( $params[ 0 ], $params[ 1 ]); }
			$stmt->execute();
			return $stmt;
		} catch ( Exception $e ) { throw new DatabaseException( $e->getMessage()); }
	}
}
class DatabaseException extends Exception {} // hush the generic Exception warning

// echo "done with Database definition. <br>";

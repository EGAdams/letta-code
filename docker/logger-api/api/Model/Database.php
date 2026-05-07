<?php
// echo "require_once config.php... <br>";
require_once  __DIR__  . "/../inc/config.php";
// echo "done requiring config.php. <br>";
class Database {
    protected $connection = null;
	public function __construct() {
        try {
            $this->connection = new mysqli( DB_HOST, DB_USERNAME, DB_PASSWORD, DB_DATABASE_NAME );
			if ( mysqli_connect_errno()) { throw new DatabaseException( "Could not connect to database." ); }
		} catch ( Exception $e ) {
		    throw new DatabaseException( $e->getMessage()); }
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
    
    public function insert( $query, $params = [] ) {
        try {
            $stmt = $this->executeStatement( $query, $params );
            $stmt->close();
            return $stmt;
        } catch ( Exception $e ) {
            throw new DatabaseException( $e->getMessage()); }
        return false;
    }

    public function delete( $query, $params = [] ) {
        try {
            $stmt = $this->executeStatement( $query, $params );
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
			if ( $params ) {
                $types = $params[ 0 ];
                $values = $params[ 1 ];
                $bindArgs = array_merge( [ $types ], $values );
                $refs = [];
                foreach ( $bindArgs as $key => $value ) {
                    $refs[ $key ] = &$bindArgs[ $key ];
                }
                call_user_func_array( [ $stmt, 'bind_param' ], $refs );
            }
			$stmt->execute();
			return $stmt;
		} catch ( Exception $e ) { throw new DatabaseException( $e->getMessage()); }
	}
}
class DatabaseException extends Exception {} // hush the generic Exception warning

// echo "done with Database definition. <br>";

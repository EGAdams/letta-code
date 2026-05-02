-- Create monitored_objects table
CREATE TABLE IF NOT EXISTS `monitored_objects` (
  `id` int(100) NOT NULL AUTO_INCREMENT,
  `object_view_id` varchar(50) COLLATE utf8_unicode_ci NOT NULL,
  `object_data` mediumtext COLLATE utf8_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `object_name` (`object_view_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

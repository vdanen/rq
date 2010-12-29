-- phpMyAdmin SQL Dump
-- version 3.1.1
-- http://www.phpmyadmin.net
--
-- Host: localhost
-- Generation Time: Mar 03, 2009 at 03:59 PM
-- Server version: 5.0.58
-- PHP Version: 5.2.6

SET SQL_MODE="NO_AUTO_VALUE_ON_ZERO";

--
-- Database: `rqs`
--

-- --------------------------------------------------------

--
-- Table structure for table `files`
--

DROP TABLE IF EXISTS `files`;
CREATE TABLE `files` (
  `f_record` INT NOT NULL auto_increment,
  `p_record` INT NOT NULL,
  `s_record` INT NOT NULL,
  `t_record` INT NOT NULL,
  `f_file` TEXT NOT NULL,
  PRIMARY KEY  (`f_record`),
  KEY `rec` USING BTREE (`p_record`),
  KEY `source` USING BTREE (`s_record`),
  KEY `trec` USING BTREE (`t_record`)
) ENGINE=MyISAM AUTO_INCREMENT=1 DEFAULT CHARSET=latin1 ;

-- --------------------------------------------------------

--
-- Table structure for table `packages`
--

DROP TABLE IF EXISTS `packages`;
CREATE TABLE IF NOT EXISTS `packages` (
  `p_record` INT NOT NULL auto_increment,
  `t_record` INT NOT NULL,
  `p_tag` text NOT NULL,
  `p_package` text NOT NULL,
  `p_version` text NOT NULL,
  `p_release` text NOT NULL,
  `p_fullname` text NOT NULL,
  `p_date` text NOT NULL,
  `p_update` tinyint DEFAULT 0,
  PRIMARY KEY  (`p_record`),
  KEY `trec` USING BTREE (`t_record`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1 AUTO_INCREMENT=1 ;

-- --------------------------------------------------------

--
-- Table structure for table `sources`
--

DROP TABLE IF EXISTS `sources`;
CREATE TABLE IF NOT EXISTS `sources` (
  `s_record` INT NOT NULL auto_increment,
  `p_record` INT NOT NULL,
  `t_record` INT NOT NULL,
  `s_type` varchar(1) NOT NULL,
  `s_file` text NOT NULL,
  PRIMARY KEY  (`s_record`),
  KEY `rec` USING BTREE (`s_record`),
  KEY `trec` USING BTREE (`t_record`)
) ENGINE=MyISAM AUTO_INCREMENT=1 DEFAULT CHARSET=latin1;

-- --------------------------------------------------------

--
-- Table structure for table `tags`
--

DROP TABLE IF EXISTS `tags`;
CREATE TABLE IF NOT EXISTS `tags` (
  `t_record` INT NOT NULL auto_increment,
  `tag` varchar(128) NOT NULL,
  `path` varchar(256) NOT NULL,
  `update_path` varchar(256) NOT NULL,
  `tdate` text NOT NULL,
  PRIMARY KEY  (`t_record`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1;


-- --------------------------------------------------------

--
-- Table structure for table `sources`
--

DROP TABLE IF EXISTS `ctags`;
CREATE TABLE IF NOT EXISTS `ctags` (
  `c_record` INT NOT NULL auto_increment,
  `p_record` INT NOT NULL,
  `s_record` INT NOT NULL,
  `t_record` INT NOT NULL,
  `c_name` varchar(256) NOT NULL,
  `c_extra` text NOT NULL,
  `c_type` varchar(64) NOT NULL,
  `c_line` varchar(64) NOT NULL,
  `c_file` text NOT NULL,
  PRIMARY KEY  (`c_record`),
  KEY `rec` USING BTREE (`c_record`),
  KEY `trec` USING BTREE (`t_record`)
) ENGINE=MyISAM AUTO_INCREMENT=1 DEFAULT CHARSET=latin1;


-- --------------------------------------------------------

--
-- Table structure for table `buildreqs`
--

DROP TABLE IF EXISTS `buildreqs`;
CREATE TABLE IF NOT EXISTS `buildreqs` (
  `b_record` INT NOT NULL auto_increment,
  `p_record` INT NOT NULL,
  `t_record` INT NOT NULL,
  `b_req` text NOT NULL,
  PRIMARY KEY  (`b_record`),
  KEY `rec` USING BTREE (`b_record`),
  KEY `trec` USING BTREE (`t_record`)
) ENGINE=MyISAM AUTO_INCREMENT=1 DEFAULT CHARSET=latin1;

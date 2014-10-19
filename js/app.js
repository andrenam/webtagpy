
var tagApp = angular.module('tagApp', [
    'ui.bootstrap', 
    'ngAnimate',
    'ngResource',
    'ipCookie',
    'angular-loading-bar',
    'angularTreeview',
    'smart-table',
    'angularFileUpload',
    'ngToast',
]);

// dont strip trailing slashes using resources
tagApp.config(['$resourceProvider', function ($resourceProvider) {
	// Don't strip trailing slashes from calculated URLs
	$resourceProvider.defaults.stripTrailingSlashes = false;
}]);


// Services using Angular-resources.js
tagApp.factory('FolderService', ['$resource',
  function($resource){
    return $resource('api/folder/:folder_id', {}, {
        get: { method: 'GET' },
    });
  }]);
tagApp.factory('FilesService', ['$resource',
  function($resource){
    return $resource('api/files/:folder_id', {}, {
        get: { method: 'GET', isArray: true },
        edit: { url: 'api/files/', method: 'PUT' },
    });
  }]);
tagApp.factory('CoverSearchService', ['$resource',
  function($resource){
    return $resource('api/coverart/search/:artist/:album', {}, {
        get: { method: 'GET' },
    });
  }]);
tagApp.factory('FileRenameService', ['$resource',
  function($resource){
    return $resource('api/files/rename/', {}, {
        post: { method: 'POST' },
    });
  }]);

  

// FileListCtrl Controller  
tagApp.controller('FileListCtrl', ['$scope', 'FolderService', 'FilesService', 'CoverSearchService', '$upload', '$timeout', '$modal', 'ipCookie', 'ngToast', 
    function ($scope, FolderService, FilesService, CoverSearchService, $upload, $timeout, $modal, ipCookie, ngToast) {
		// initialize/reset all data
		$scope.resetData = function() {
			$scope.folder_data = {};
			$scope.folder_tree_data = [];
			$scope.file_grid = {
				data: [],
			}
			$scope.file_grid_selection = [];
			$scope.file_grid_selection_tags = {};
			$scope.coverArtUploadFiles = [];
			$scope.coverArtUploadFilesDataUrls = [];
			$scope.coverArtSearchResult = '';
		}
		
		// watch for changes in folder_data.files.isSelected
		$scope.$watch('file_grid.data', function (newValue, oldValue) {
			$scope.file_grid_selection = []
			for (var i=0;i<$scope.file_grid.data.length;i++) {
				
				if ($scope.file_grid.data[i] && 
						"isSelected" in $scope.file_grid.data[i] && 
						$scope.file_grid.data[i].isSelected) {
					$scope.file_grid_selection.push($scope.file_grid.data[i]);
				}
			}
			$scope.changeFileSelection();
		}, true);
		
		// select/deselect all files
		$scope.selectAllFiles = function(v) {
			for (var i=0;i<$scope.file_grid.data.length;i++) {
				$scope.file_grid.data[i].isSelected = v;
			}
		};
		
		
		// update form when selection of file changes
		$scope.changeFileSelection = function() {
			$scope.clearCoverArtUpload();
			$scope.file_grid_selection_tags = { };
			if ($scope.file_grid_selection.length == 0) {
				$scope.file_grid_selection_tags = { 
					coverurl: '//:0' ,
					coverexport: 1 ,
				};
			}
			else {
				var variables = {};
				for (var i=0; i<$scope.file_grid_selection.length; i++) {
					for (var prop in $scope.file_grid_selection[i].tags) {
						if (prop != 'cover') {
							variables[prop] = prop;
						}
					}
				}
				
				for (var variable in variables) {
					var _value = '';
					for (var i=0; i<$scope.file_grid_selection.length; i++) {
						if (variable in $scope.file_grid_selection[i].tags) {
							if (_value == '') 
								_value = $scope.file_grid_selection[i].tags[variable]
							else if (_value != $scope.file_grid_selection[i].tags[variable])
								_value = '<keep>';
						}
						else {
							_value = '<keep>';
						}
					}
					
					$scope.file_grid_selection_tags[variable] = _value;
				}
				
				var _covermd5sum = '';
				var _coverurl = '//:0';
				for (var i=0; i<$scope.file_grid_selection.length; i++) {
					if (_covermd5sum == '' 
						&& 'cover' in $scope.file_grid_selection[i].tags
						&& $scope.file_grid_selection[i].tags.cover
						&& 'md5sum' in $scope.file_grid_selection[i].tags.cover
						&& $scope.file_grid_selection[i].tags.cover.md5sum) {
						_covermd5sum = $scope.file_grid_selection[i].tags.cover.md5sum;
						_coverurl = 'api/coverart/'+$scope.file_grid_selection[i].file_id + '?' + new Date().getTime();
					}
					else if (_covermd5sum != ''
						&& 'cover' in $scope.file_grid_selection[i].tags
						&& $scope.file_grid_selection[i].tags.cover
						&& 'md5sum' in $scope.file_grid_selection[i].tags.cover
						&& _covermd5sum != $scope.file_grid_selection[i].tags.cover.md5sum) {
						_covermd5sum = '<keep>';
						_coverurl = '//:0';
					}
				}
				$scope.file_grid_selection_tags.coverurl = _coverurl;
				$scope.file_grid_selection_tags.covermd5sum = _covermd5sum;
				
				if ($scope.file_grid_selection.length == $scope.folder_data.files.length) {
					$scope.file_grid_selection_tags.coverexport = 1;
				}
				else {
					$scope.file_grid_selection_tags.coverexport = 0;
				}
			}
		};
		


		// select cover image to upload
		$scope.onCoverFileSelect = function($files) {
			//$files: an array of files selected, each file has name, size, and type.
			$scope.coverArtSearchResult = '';
			$scope.coverArtUploadFiles = $files;
			$scope.coverArtUploadFilesDataUrls = [];
			if ($scope.coverArtUploadFiles.length > 0) {
				var f = $files[0];
				if (window.FileReader != null && (window.FileAPI == null || FileAPI.html5 != false) && f.type.indexOf('image') > -1) {
					var fileReader = new FileReader();
					fileReader.readAsDataURL($files[0]);
					var loadFile = function(fileReader, index) {
						fileReader.onload = function(e) {
							$timeout(function() {
								$scope.coverArtUploadFilesDataUrls[index] = e.target.result;
							});
						}
					}(fileReader, 0);
				}
			}
		};
		// un-select/clear cover image upload and online results
		$scope.clearCoverArtUpload = function() {
			$scope.coverArtSearchResult = '';
			$scope.coverArtUploadFiles = [];
			$scope.coverArtUploadFilesDataUrls = [];
			$files = [];
		}
		
		
		// search cover art via google image search
		$scope.searchCoverArt = function(artist, album) {
			$scope.coverArtUploadFiles = [];
			$scope.coverArtUploadFilesDataUrls = [];
			$files = [];
			$scope.coverArtSearchResult = '';
			CoverSearchService.get( {artist: artist, album: album }, {},
				function (data) {
					var modalInstance = $modal.open({
					  templateUrl: 'coverArtSearch.html',
					  controller: 'CoverArtSearchCtrl',
					  size: 'sm',
					  resolve: {
						coverArtSearchResult: function () { 
							return data.coverarturl;
						}
					  }
					});

					modalInstance.result.then(function (coverArtSearchResult) {
						$scope.coverArtSearchResult = coverArtSearchResult;
					});
				}, function (error) {
					ngToast.create({
						class: 'warning',
						content: "No cover art found for album '"+album+"'",
					});
				});
		};


		// save tag form to selected files
		$scope.saveTags = function() {
			if ( $scope.file_grid_selection.length == 0 ) {
				return false;
			}
			var file_ids = [];
			for (var i=0; i<$scope.file_grid_selection.length; i++) {
				file_ids.push($scope.file_grid_selection[i].file_id);
			}
			var data = {
				file_ids: file_ids,
				tags: $scope.file_grid_selection_tags,
				coverArtSearchResult: $scope.coverArtSearchResult,
			}
			
			if ($scope.coverArtUploadFiles.length == 1) {
				$scope.upload = $upload.upload({
					url: 'api/files/',
					method: 'PUT',
					data: data,
					file: $scope.coverArtUploadFiles[0],
					}).progress(function(evt) {
						//console.log('percent: ' + parseInt(100.0 * evt.loaded / evt.total));
					}).success(function(data, status, headers, config) {
						// file is uploaded successfully
						ngToast.create({
							class: 'success',
							content: 'Saved tags',
						});

					
						// re-load directory data
						//$scope.reloadFiles();
						$scope.changeFolder($scope.folder_data.folder_id);
						$scope.clearCoverArtUpload();
				});		
			}
			else {
				FilesService.edit({}, data, function(data) {
					ngToast.create({
						class: 'success',
						content: 'Saved tags',
					});
					
					// re-load directory data
					//$scope.reloadFiles();
					$scope.changeFolder($scope.folder_data.folder_id);
					$scope.clearCoverArtUpload();
					
				}, function(error) {
					ngToast.create({
						class: 'danger',
						content: 'Could not save tags',
					});

					// re-load directory data
					//$scope.reloadFiles();
					$scope.changeFolder($scope.folder_data.folder_id);
					$scope.clearCoverArtUpload();
				});
			}
		}
		
		
		// recursively build tree data
		buildTreeData = function buildTreeDataFn(folders) {
			var treeData = [];
			for (var i=0;i<folders.length;i++) {
				var children = [];
				if (folders[i].folders.length > 0) {
					var subfolders = folders[i].folders;
					children = buildTreeDataFn(subfolders);
				}
				
				var folderData = {
					'folder_name': folders[i].folder_name,
					'folder_id': folders[i].folder_id,
					'folder_path': folders[i].folder_path,
					'collapsed': false,
					'children': children
				};
				treeData.push(folderData);
			}
			
			return treeData;
		};
		
		// change folder without an id
		$scope.changeFolderPath = function(folder_path) {
			var folder_id = window.btoa(folder_path);
			$scope.changeFolder(folder_id);
		}
		
		// switch to folder 'folder_id'
		$scope.changeFolder = function(folder_id) {
			// initialize and reset data
			$scope.resetData();
			
			// load files and folders 
			FolderService.get(
				{'folder_id': folder_id},
				function (data) {
					// save folder_id to cookie
					ipCookie('webtagpy_folder_id', folder_id, { expires: 180 });
					
					// assign loaded files and folders to scope
					$scope.folder_data = data;
					// assign to grid
					$scope.file_grid.data = data.files;
					// recursively build tree data
					$scope.folder_tree_data = buildTreeData(data.folders);					
				}).$promise
				.then(function (data) {
					// chain loading of tag data
					return FilesService.get( 
							{'folder_id': $scope.folder_data.folder_id},
							function (data) {
								// assign tag data to scope
								$scope.folder_data.files = data;
								// assign to grid
								$scope.file_grid.data = data;
							}).$promise;
				});
		}
		
		/*// soft-reload files in this folder without resetting the selection and folder-tree
		$scope.reloadFiles = function() {
			if ('folder_id' in $scope.folder_data && $scope.folder_data.folder_id) {
				// chain loading of tag data
				FilesService.get( 
						{'folder_id': $scope.folder_data.folder_id},
						function (data) {
							// assign tag data to scope
							$scope.folder_data.files = data;
				});
			}
		}*/
		
        // initially load files and folders in "default directory"
        if (ipCookie('webtagpy_folder_id') !== undefined) {
			$scope.changeFolder(ipCookie('webtagpy_folder_id'));
		}
		else {
			$scope.changeFolder('');
		}
		
		
		// watch for changes in folder tree selection
		// and change folder if necessary
		$scope.$watch('folder_tree.currentNode', function() {
			if ($scope.folder_tree.currentNode && 
				'folder_id' in $scope.folder_tree.currentNode &&
				$scope.folder_tree.currentNode.folder_id &&
				'folder_id' in $scope.folder_data &&
				$scope.folder_data.folder_id && 
				$scope.folder_tree.currentNode.folder_id != $scope.folder_data.folder_id) {
					
					// change folder
					$scope.changeFolder($scope.folder_tree.currentNode.folder_id);
			}
		});
		
		
		// open modal dialog for file renaming
		$scope.renameFiles = function() {
			if ($scope.file_grid_selection.length > 0) {
				
				// open modal dialog
				var modalInstance = $modal.open({
				  templateUrl: 'renameFiles.html',
				  controller: 'RenameFilesCtrl',
				  resolve: {
					selected_files: function () { 
						return $scope.file_grid_selection;
					}
				  }
				});

				modalInstance.result.then(function (result) {
					// TODO: reload files
					// re-load directory data
					//$scope.reloadFiles();
					$scope.changeFolder($scope.folder_data.folder_id);
					$scope.clearCoverArtUpload();					
				});

			}
		};

    }]);



tagApp.controller('CoverArtSearchCtrl', ['$scope', '$modalInstance', 'coverArtSearchResult', 
	function ($scope, $modalInstance, coverArtSearchResult) {
		$scope.coverArtSearchResult = coverArtSearchResult;

		$scope.ok = function () {
			$modalInstance.close($scope.coverArtSearchResult);
		};

		$scope.cancel = function () {
			$modalInstance.dismiss('cancel');
		};
	}]);


tagApp.controller('RenameFilesCtrl', ['$scope', '$modalInstance', '$timeout', 'ipCookie', 'selected_files', 'FileRenameService', 'ngToast', 
	function ($scope, $modalInstance, $timeout, ipCookie, selected_files, FileRenameService, ngToast) {
		$scope.selected_files = selected_files;
		$scope.file_ids = [];
		for (var i=0; i<$scope.selected_files.length;i++) {
			$scope.file_ids.push($scope.selected_files[i].file_id);
		}
		
		// load rename_format from cookie
		$scope.rename_format = ipCookie('webtagpy_rename_format');
		if ($scope.rename_format === undefined || !$scope.rename_format) {
			$scope.rename_format = '%(artist)s - %(tracknumber)02d - %(title)s';
		}
		
		$scope.rename_results = [];
		$scope.invalid_rename_format = false;
		$scope.did_rename = false;
		
		$scope.preview = function() {
			FileRenameService.post({}, {
				'file_ids': $scope.file_ids,
				'rename_format': $scope.rename_format,
				'dry_run': true,
			}, function (data) {
				$scope.rename_results = data.rename_results;
				$scope.invalid_rename_format = false;
			}, function (error) {
				$scope.rename_results = [];
				$scope.invalid_rename_format = true;
			});
		};
		
		
		$scope.doRename = function() {
			// preview first to validate the rename format
			FileRenameService.post({}, {
				'file_ids': $scope.file_ids,
				'rename_format': $scope.rename_format,
				'dry_run': true,
				},
				function (data) {
					$scope.rename_results = data.rename_results;
					$scope.invalid_rename_format = false;
				}).$promise
				.then(function (data) {
					// rename files 
					return FileRenameService.post({}, {
						'file_ids': $scope.file_ids,
						'rename_format': $scope.rename_format,
						'dry_run': false,
						},
						function (data) {
							$scope.rename_results = data.rename_results;
							$scope.invalid_rename_format = false;
							$scope.did_rename = true;
							
							ngToast.create({
								class: 'success',
								content: 'Renamed files',
							});

							
							// delay-close the modal dialog
							$timeout(function () {
								$modalInstance.close('');
							}, 1000);
						}).$promise;
				});
		};
		
		
		var timeoutPromise;
		$scope.$watch('rename_format', function(newValue, oldValue) {
			$timeout.cancel(timeoutPromise);
			timeoutPromise = $timeout(function () {
				ipCookie('webtagpy_rename_format', $scope.rename_format, { expires: 180 });
				$scope.preview();
			}, 500);
		});
		$scope.preview();

		$scope.cancel = function () {
			$modalInstance.dismiss('cancel');
		};
	}]);

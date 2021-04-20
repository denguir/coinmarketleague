// Call the dataTables jQuery plugin
$(document).ready(function() {
  $('#dataTable').DataTable();
});


$(document).ready( function() {
  $('#dataTable_filter').dataTable( {
    "language": {
      "search": "Apply filter _INPUT_ to table"
    }
  });
});


$(document).ready( function() {
  $('#dataTable_length').dataTable( {
    "language": {
      "lengthMenu": 'Display <select>'+
        '<option value="10">10</option>'+
        '<option value="20">20</option>'+
        '<option value="30">30</option>'+
        '<option value="40">40</option>'+
        '<option value="50">50</option>'+
        '<option value="-1">All</option>'+
        '</select> records'
    }
  } );
} );

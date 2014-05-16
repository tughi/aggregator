/** @jsx React.DOM */

var Entry = React.createClass({
	render: function () {
        var date = moment(this.props.data.updated);
        var now = moment();
        var dateFormat = now.year() != date.year() ? "MMM DD YYYY" : now.date() == date.date() && now.month() == date.month() ? "hh:mm a" : "MMM DD";

        console.log(this.props.feeds);

		return (
		    <div className="entry">
		        <div id="header">
		            <div id="title-wrapper">
		                <span id="title">{this.props.data.title || 'Loading...'}</span>
		            </div>
		            <div id="date-wrapper">
		                <span id="fadeout"></span><span id="date">{date.format(dateFormat)}</span>
		            </div>
		            <div id="toggle"></div>
		            <a id="favicon" target="_blank" href={this.props.data.link} style={{'background-image': 'url("' + this.props.feeds[this.props.data.feed_id].favicon + '")'}}></a>
		            <span id="star"></span>
		        </div>
		        <div id="body">
		            <div id="content">
		                <div id="content-header">
		                    <h1><a id="title"></a></h1>
		                    <div>
		                        <span id="author-container">by <span id="author"></span>,</span>
		                        <a id="feed"></a>
		                        <span id="date-container">on <span id="date"></span></span>
		                        <span id="star" onclick="javascript: return false"></span>
		                    </div>
		                    <div id="tags">
		                        <div id="arrow"></div><div id="toggle-read">keep </div><div id="toggle">close</div>
		                    </div>
		                </div>
		            </div>
		            <div id="footer">
		            </div>
		        </div>
		    </div>
		);
	}
});

var Session = React.createClass({
	getInitialState: function () {
		return {feeds: {}, entries: []};
	},
	componentWillMount: function () {
		$.ajax({
			url: this.props.url,
			dataType: 'json',
			success: function (data) {
				this.setState({feeds: data.feeds});

				if (data.entries) {
					var entries = [];
					data.entries.map(function (id) {
						entries.push({id: id});
					});

					// fetch first page
					this.fetchPage(0, entries);
				}
			}.bind(this)
		});
	},
	fetchPage: function (page, entries) {
		var pageStart = page * 50;
		var pageEnd = (page + 1) * 50;

		var ids = [];
		(entries || this.state.entries).slice(pageStart, pageEnd).map(function (entry) {
			ids.push(entry.id);
		});

		$.ajax({
			url: 'api/entries',
			data: {ids: ids.join(',')},
			success: function (data) {
				var newEntries = entries || this.state.entries;
				var index = pageStart;
				while (index < pageEnd) {
					newEntries[index] = data[index++ % 50];
				}

				this.setState({entries: newEntries});
			}.bind(this)
		});
	},
	render: function () {
		var entryNodes = this.state.entries.map(function (entry) {
			return <Entry key={entry.id} data={entry} feeds={this.state.feeds} />;
		}.bind(this));

		return (
			<div id="entries">
				{entryNodes}
			</div>
		);
	}
});

$("body").addClass(navigator.userAgent.match(/Android|iPhone|iPad|iPod/i) ? "mobile" : "desktop");

React.renderComponent(<Session url="reader/session" />, document.body);
